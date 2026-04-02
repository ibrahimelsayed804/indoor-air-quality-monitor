# Indoor Air Quality Monitor

Raspberry Pi-based multi-node air quality monitoring system with real-time
data logging, built as a Final Year Project at the University of Wollongong 
in Malaysia.

## What It Does
- Reads CO2, temperature & humidity from up to **10 SCD41 sensors**
  across 2 TCA9548A I2C multiplexers (0x70, 0x71)
- Auto-detects an **FS3000 airflow sensor** on any mux channel
- Stores all sensor data to **MariaDB** with duplicate-safe INSERT IGNORE
- Exports rolling **CSV master files** hourly with deduplication checkpointing
- Runs continuously on Raspberry Pi with graceful shutdown handling

## Hardware
- Raspberry Pi
- SCD41 CO2 / Temperature / Humidity sensors (×10)
- FS3000 airflow sensor
- TCA9548A I2C multiplexers (×2)

## Stack
- Python 3, adafruit-circuitpython-scd4x, adafruit-circuitpython-tca9548a
- smbus2, qwiic-fs3000, mysql-connector-python
- MariaDB (MySQL), CSV logging

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Set up the database: `mysql -u root -p < schema.sql`
3. Configure mux addresses and channels in `data_collection.py`
4. Run: `python3 data_collection.py`

## Author
Ibrahim Said Hussein Elsayed  
Robotics & Embedded Systems Engineer — Dubai, UAE  
[LinkedIn](https://www.linkedin.com/in/ibrahim-said-hussein-elsayed)
