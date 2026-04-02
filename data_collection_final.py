

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#"""
#IAQ Logger for Thonny (Raspberry Pi)\
- SCD41 sensors behind two TCA9548A I2C muxes (0x70, 0x71) on selectable channels\
- FS3000 airflow sensor auto-detected on ANY mux channel\
- Logs to MariaDB (MySQL) and appends to rolling CSV "master" files\
- Guaranteed no duplicate rows in DB (UNIQUE(timestamp) + INSERT IGNORE)\
- Guaranteed no duplicate rows in CSVs (reads last timestamp already written)\
- Sampling is throttled to SAMPLE_PERIOD_SEC (default 300s) regardless of loop rate\
Tested for Python 3 on Raspberry Pi OS with Thonny.
#"""


import os, time, csv, sys
import board, busio
from smbus2 import SMBus
from datetime import datetime, timedelta\
import mysql.connector

from adafruit_tca9548a import TCA9548A\
import adafruit_scd4x

import qwiic_i2c
import qwiic_fs3000

# =========================
# USER CONFIG
# =========================

# Which muxes are present and which channels hold SCD41 devices:
SCD41_CHANNELS = {
    0x70: [2, 3, 4, 5, 6, 7],   # 6 sensors on mux 0x70
    0x71: [2, 3, 4, 5, 6, 7],   # 6 sensors on mux 0x71
    }

# FS3000 settings
FS3000_I2C_ADDR = 0x28            # default FS3000 address
FS3000_MODEL_RANGE = 7            # 7 for FS3000-1005 (7 m/s) or 15 for FS3000-1015 (15 m/s)
FS3000_SCAN_CHANNELS = list(range(8))   # channels to scan on each mux for FS3000 (0..7)

# Database configuration (MariaDB / MySQL)
DB_CONFIG = dict(
    host="localhost",
    user="root",
    password="root123",
    database="sensor_db",
)

# CSV output directory (created if not exists)\
CSV_DIR = "./"   # change if you want a dedicated folder, e.g., "./csv_out"

# Sampling throttle: read + write at most once every X seconds
SAMPLE_PERIOD_SEC = 300  # = 5 minutes


# =========================
# HELPERS
# =========================

def ensure_dir(path: str):
    if path and path != ".":
        os.makedirs(path, exist_ok=True)


def read_last_timestamp_from_csv(csv_path: str):
    """Return the last timestamp (as datetime) present in an existing master CSV.\
    If file doesn't exist or has only header/empty, return datetime.min.\
    """
    if not os.path.isfile(csv_path):
        return datetime.min
    try:
        with open(csv_path, "r", newline="") as f:
            r = csv.reader(f)
            rows = list(r)
            # Expect header in row0, data afterwards
            for row in reversed(rows[1:]):
                if not row:
                    continue
                try:
                    ts = row[0].strip()
                    # Try common formats
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                        try:
                            return datetime.strptime(ts, fmt)\
                        except ValueError:
                            pass
                except Exception:
                    continue
    except Exception as e:
        print(f"WARNING: Failed reading \{csv_path\} for last timestamp: \{e\}")
    return datetime.min


def dt_to_str(dt: datetime) -> str:\
    return dt.strftime("%Y-%m-%d %H:%M:%S")\


# =========================
# I2C / MUX SETUP
# =========================

print("Setting up I2C and muxes...")
print("Running script:", os.path.abspath(__file__))  # verify correct file is running

i2c = busio.I2C(board.SCL, board.SDA)
MUXES = \{\}\
for addr in SCD41_CHANNELS.keys():
    try:\
        MUXES[addr] = TCA9548A(i2c, address=addr)\
        print(f" - Mux 0x\{addr:02X\} OK")\
    except Exception as e:\
        print(f"WARNING: Mux 0x\{addr:02X\} init failed: \{e\}")\
\
# raw SMBus for direct mux channel flips when needed (e.g., FS3000 scan)\
smb = SMBus(1)\
\
\
def tca_select_one(mux_addr: int, ch: int):\
    """Select exactly one channel on the given mux (one-hot)."""\
    if not (0 <= ch <= 7):\
        raise ValueError("Channel must be 0..7")\
    smb.write_byte_data(mux_addr, 0x00, 1 << ch)\
    # Small settle delay for the analog switches\
    time.sleep(0.02)\
\
\
def tca_disable_all(mux_addr: int):\
    """Disable all channels on given mux (write 0 mask)."""\
    smb.write_byte_data(mux_addr, 0x00, 0x00)\
    time.sleep(0.02)\
\
\
# =========================\
# SCD41 SETUP\
# =========================\
\
print("Probing SCD41 sensors...")\
sensors = []  # list of dicts: \{"mux": int, "channel": int, "device": SCD4X\}\
for mux_addr, channels in SCD41_CHANNELS.items():\
    mux = MUXES.get(mux_addr)\
    if mux is None:\
        continue\
    for ch in channels:\
        try:\
            dev = adafruit_scd4x.SCD4X(mux[ch])\
            dev.start_periodic_measurement()\
            sensors.append(\{"mux": mux_addr, "channel": ch, "device": dev\})\
            time.sleep(0.05)\
            print(f" - Sensor @ mux 0x\{mux_addr:02X\} ch\{ch\}: OK")\
        except Exception as e:\
            print(f"WARNING: No SCD41 on mux 0x\{mux_addr:02X\} ch\{ch\}: \{e\}")\
\
if not sensors:\
    print("WARNING: No SCD41 sensors found. Continuing for FS3000 only...")\
\
print("Warming up SCD41 sensors (waiting for first data_ready)...")\
t0 = time.time()\
while sensors and not all(s["device"].data_ready for s in sensors):\
    if time.time() - t0 > 30:\
        print("...still warming, continuing anyway.")\
        break\
    time.sleep(0.5)\
print("SCD41 warmup done.")\
\
\
# =========================\
# FS3000 AUTO-DETECT\
# =========================\
\
def init_fs3000_on_path(mux_addr: int, ch: int):\
    """Try to init FS3000 at the specified mux/channel path. Return (fs_obj or None)."""\
    try:\
        # Select path\
        tca_select_one(mux_addr, ch)\
\
        # SparkFun Qwiic driver expects the bus to be available; selecting mux path is enough\
        qwiic_drv = qwiic_i2c.getI2CDriver()\
        fs = qwiic_fs3000.QwiicFS3000(address=FS3000_I2C_ADDR, i2c_driver=qwiic_drv)\
\
        if not fs.begin():\
            return None\
\
        if FS3000_MODEL_RANGE == 7:\
            fs.set_range(fs.kAirflowRange7Mps)\
        elif FS3000_MODEL_RANGE == 15:\
            fs.set_range(fs.kAirflowRange15Mps)\
        else:\
            print("Unknown FS3000 range configured; defaulting to 7 m/s.")\
            fs.set_range(fs.kAirflowRange7Mps)\
\
        print(f"FS3000 detected at mux 0x\{mux_addr:02X\} ch\{ch\}.")\
        return fs\
    except Exception:\
        return None\
    finally:\
        pass\
\
\
def autodetect_fs3000():\
    """Scan all configured muxes + channels to find an FS3000. Returns (fs_obj, mux_addr, ch) or (None, None, None)."""\
    print("Scanning for FS3000 on all mux channels...")\
    for mux_addr in MUXES.keys():\
        for ch in FS3000_SCAN_CHANNELS:\
            fs = init_fs3000_on_path(mux_addr, ch)\
            if fs is not None:\
                return fs, mux_addr, ch\
    print("No FS3000 detected on any mux/channel.")\
    return None, None, None\
\
\
fs, FS_MUX_ADDR, FS_CH = autodetect_fs3000()\
\
\
# =========================\
# DB SETUP
# =========================\

print("Connecting to MariaDB/MySQL...")
db = mysql.connector.connect(**DB_CONFIG)
cursor = db.cursor()

# airflow table
cursor.execute("""
CREATE TABLE IF NOT EXISTS fs3000 (
  id INT AUTO_INCREMENT PRIMARY KEY,
  timestamp DATETIME NOT NULL,
  air_velocity FLOAT NOT NULL,
  UNIQUE KEY (timestamp)
) ENGINE=InnoDB;
""")
db.commit()

# scd41 tables, one per detected sensor
for idx, _ in enumerate(sensors, start=1):
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS scd41_\{idx\} (
      id INT AUTO_INCREMENT PRIMARY KEY,\
      timestamp DATETIME NOT NULL,\
      co2 FLOAT NOT NULL,\
      temperature FLOAT NOT NULL,\
      humidity FLOAT NOT NULL,\
      UNIQUE KEY (timestamp)\
    ) ENGINE=InnoDB;\
    """)
db.commit()
\
\
# =========================
# CSV PREP (DEDUP SAFE)
# =========================

ensure_dir(CSV_DIR)

N = len(sensors)
table_names   = [f"scd41_\{i\}" for i in range(1, N+1)]\
master_paths  = [os.path.join(CSV_DIR, f"scd41_\{i\}_master.csv") for i in range(1, N+1)]\
last_exports  = [read_last_timestamp_from_csv(master_paths[i]) for i in range(N)]\

fs_master_path = os.path.join(CSV_DIR, "fs3000_master.csv")\
last_export_fs = read_last_timestamp_from_csv(fs_master_path)\

print("Initial last-export checkpoints:")
for i in range(N):\
    print(f" - \{table_names[i]} last CSV timestamp: \{dt_to_str(last_exports[i]) if last_exports[i] != datetime.min else 'NONE'\}")
print(f" - fs3000 last CSV timestamp: \{dt_to_str(last_export_fs) if last_export_fs != datetime.min else 'NONE'}")


def append_new_rows_to_csv(table_name: str, csv_path: str, since: datetime):\
    """Append NEW rows from DB table to csv_path. Returns new 'since' checkpoint (now)."""
    now = datetime.now()
    cursor.execute(f"""
        SELECT timestamp, co2, temperature, humidity
        FROM {table_name}
        WHERE timestamp > %s AND timestamp <= %s
        ORDER BY timestamp ASC
    """, (dt_to_str(since), dt_to_str(now)))\
    rows = cursor.fetchall()
    if not rows:
        return now

    file_exists = os.path.isfile(csv_path)
    with open(csv_path, "a", newline="") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(["timestamp", "CO2 (ppm)", "Temp (C)", "Humidity (%)"])
        w.writerows(rows)
    print(f"[{now.strftime('%H:%M:%S')\}] Appended {len(rows)} rows to {os.path.basename(csv_path)\}")
    return now


def append_new_rows_to_csv_fs(csv_path: str, since: datetime):
    now = datetime.now()
    cursor.execute("""
        SELECT timestamp, air_velocity
        FROM fs3000\
        WHERE timestamp > %s AND timestamp <= %s\
        ORDER BY timestamp ASC
    """, (dt_to_str(since), dt_to_str(now)))
    rows = cursor.fetchall()
    if not rows:
        return now

    file_exists = os.path.isfile(csv_path)
    with open(csv_path, "a", newline="") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(["timestamp", "air_velocity (m/s)"])
        w.writerows(rows)
    print(f"[{now.strftime('%H:%M:%S')}] Appended {len(rows)} rows to {os.path.basename(csv_path)\}")
    return now


# One-time export on startup (based on dedup checkpoints)\
for i in range(N):\
    last_exports[i] = append_new_rows_to_csv(table_names[i], master_paths[i], last_exports[i])
last_export_fs = append_new_rows_to_csv_fs(fs_master_path, last_export_fs)

next_export = datetime.now() + timedelta(hours=1)


# =========================
# MAIN LOOP (THROTTLED)\
# =========================

print("Entering main loop. Press Ctrl+C to stop.")
# schedule first sample immediately on start:
next_sample = datetime.now()

try:
    while True:
        now = datetime.now()

        # Hourly CSV exports (dedup-safe) '97 independent of sampling cadence
        if now >= next_export:
            for i in range(N):
                last_exports[i] = append_new_rows_to_csv(table_names[i], master_paths[i], last_exports[i])
            last_export_fs = append_new_rows_to_csv_fs(fs_master_path, last_export_fs)
            next_export = now + timedelta(hours=1)

        # If it's not time to sample yet, sleep shortly and loop
        if now < next_sample:
            time.sleep(1)  # keep CPU light; adjust if desired
            continue

        # ========== It IS time to take a sample ==========
        ts_str = dt_to_str(now)

        # Read & store SCD41s
        for idx, s in enumerate(sensors, start=1):
            dev = s["device"]
            try:
                # We'll try to read when data_ready, otherwise skip gracefully
                if dev.data_ready:
                    co2 = float(dev.CO2)  # Adafruit SCD4x uses 'CO2'
                    tmp = float(dev.temperature)
                    hum = float(dev.relative_humidity)
                    print(f"[{ts_str\}][Sensor #{idx} @ mux 0x{s['mux']:02X} ch{s['channel']}] "
                          f"CO2: {co2:.0f} ppm | T: \{tmp:.2f\} 'b0C | RH: {hum:.2f} %")
                    cursor.execute(
                        f"INSERT IGNORE INTO scd41_\{idx\} (timestamp, co2, temperature, humidity) "
                        f"VALUES (%s,%s,%s,%s)",
                        (ts_str, co2, tmp, hum)
                    )
                else:
                    print(f"[\{ts_str\}][Sensor #\{idx\}] data not ready; skipped this cycle.")
            except Exception as e:
                print(f"SCD41 read/store error (sensor \{idx\}): \{e\}")

        # Read & store FS3000 (if found)
        if fs is not None:
            try:
                # Re-select the correct mux path on every read in case something changed it
                tca_select_one(FS_MUX_ADDR, FS_CH)
                v = float(fs.read_meters_per_second())
                print(f"[{ts_str}][FS3000 @ mux 0x{FS_MUX_ADDR:02X} ch{FS_CH}] Air velocity: {v:.3f} m/s")
                cursor.execute(
                    "INSERT IGNORE INTO fs3000 (timestamp, air_velocity) VALUES (%s,%s)",
                    (ts_str, v)
                )
            except Exception as e:
                print("FS3000 read/store error:", e)

        # Commit batched inserts for this sample
        try:
            db.commit()
        except Exception as e:
            print("DB commit error:", e)

        # Schedule next sample exactly SAMPLE_PERIOD_SEC later
        next_sample = now + timedelta(seconds=SAMPLE_PERIOD_SEC)

except KeyboardInterrupt:
    print("\\nStopping...")

except Exception as e:
    print("Fatal error:", e)

finally:
    try:
        for mux_addr in MUXES.keys():
            tca_disable_all(mux_addr)
    except Exception:
        pass
    try:
        smb.close()
    except Exception:
        pass
    try:
        cursor.close()
        db.close()
    except Exception:
        pass}
