# Indoor Air Quality Monitor

A Raspberry Pi-based multi-node air quality monitoring system with real-time
data logging to MariaDB and CSV. Built as a Final Year Project at the
University of Wollongong in Malaysia.

---

## What It Does

- Reads **CO2, temperature & humidity** from up to 10 SCD41 sensors across
  2 TCA9548A I2C multiplexers (addresses 0x70 and 0x71)
- Auto-detects an **FS3000 airflow sensor** on any mux channel — no manual
  config needed
- Stores all readings to **MariaDB** using duplicate-safe `INSERT IGNORE`
- Exports **rolling CSV master files** hourly with deduplication checkpointing
  so no duplicate rows are ever written, even after a restart
- Runs continuously with graceful shutdown (Ctrl+C cleans up I2C bus and DB
  connection)

---

## Hardware

| Component | Quantity |
|---|---|
| Raspberry Pi | 1 |
| SCD41 CO2 / Temperature / Humidity sensor | up to 10 |
| TCA9548A I2C multiplexer | 2 |
| FS3000 airflow sensor | 1 |

---

## Software Stack

- Python 3
- `adafruit-circuitpython-scd4x` — SCD41 driver
- `adafruit-circuitpython-tca9548a` — I2C mux driver
- `smbus2` — low-level I2C channel switching
- `sparkfun-qwiic-fs3000` — airflow sensor driver
- `mysql-connector-python` — MariaDB interface
- MariaDB (MySQL) — time-series sensor storage
- CSV — rolling backup export

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/ibrahim-said/indoor-air-quality-monitor.git
cd indoor-air-quality-monitor
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up the database
```bash
mysql -u root -p < schema.sql
```

### 4. Configure your sensors
Open `data_collection.py` and edit the `USER CONFIG` section:
```python
SCD41_CHANNELS = {
    0x70: [2, 3, 4, 5, 6, 7],   # channels with SCD41 on mux 0x70
    0x71: [2, 3, 4, 5, 6, 7],   # channels with SCD41 on mux 0x71
}
```

Also update `DB_CONFIG` with your MariaDB credentials.

### 5. Run
```bash
python3 data_collection.py
```

---

## Data Output

**MariaDB tables created automatically:**
- `fs3000` — airflow readings (timestamp, air_velocity m/s)
- `scd41_1` through `scd41_N` — one table per detected sensor (timestamp, co2 ppm, temperature °C, humidity %)

**CSV files written to `./` by default:**
- `fs3000_master.csv`
- `scd41_1_master.csv` … `scd41_N_master.csv`

CSV exports happen once on startup and then every hour. Duplicate rows are
prevented by tracking the last exported timestamp per file.

---

## Project Structure

```
indoor-air-quality-monitor/
├── data_collection.py     # main data logging script
├── schema.sql             # MariaDB table definitions
├── requirements.txt       # Python dependencies
├── README.md
├── docs/
│   └── system_diagram.png # hardware wiring diagram (add your own)
└── sample_data/
    └── scd41_1_sample.csv # example CSV output
```

---

## Author

**Ibrahim Said Hussein Elsayed**  
Robotics & Embedded Systems Engineer — Dubai, UAE  
[LinkedIn](https://www.linkedin.com/in/ibrahim-said-hussein-elsayed)
