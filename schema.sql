-- Indoor Air Quality Monitor — Database Schema
-- Run: mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS sensor_db;
USE sensor_db;

-- FS3000 airflow sensor table
CREATE TABLE IF NOT EXISTS fs3000 (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  timestamp     DATETIME NOT NULL,
  air_velocity  FLOAT NOT NULL,
  UNIQUE KEY (timestamp)
) ENGINE=InnoDB;

-- SCD41 sensor tables (one per sensor, up to 10)
-- Mux 0x70: channels 2-7 → sensors 1-6
-- Mux 0x71: channels 2-7 → sensors 7-12 (extend as needed)

CREATE TABLE IF NOT EXISTS scd41_1 (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  timestamp   DATETIME NOT NULL,
  co2         FLOAT NOT NULL,
  temperature FLOAT NOT NULL,
  humidity    FLOAT NOT NULL,
  UNIQUE KEY (timestamp)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS scd41_2 LIKE scd41_1;
CREATE TABLE IF NOT EXISTS scd41_3 LIKE scd41_1;
CREATE TABLE IF NOT EXISTS scd41_4 LIKE scd41_1;
CREATE TABLE IF NOT EXISTS scd41_5 LIKE scd41_1;
CREATE TABLE IF NOT EXISTS scd41_6 LIKE scd41_1;
CREATE TABLE IF NOT EXISTS scd41_7 LIKE scd41_1;
CREATE TABLE IF NOT EXISTS scd41_8 LIKE scd41_1;
CREATE TABLE IF NOT EXISTS scd41_9 LIKE scd41_1;
CREATE TABLE IF NOT EXISTS scd41_10 LIKE scd41_1;
