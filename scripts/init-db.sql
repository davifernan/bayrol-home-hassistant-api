-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create hypertable for sensor_readings after tables are created
-- This will be executed after SQLAlchemy creates the tables
DO $$
BEGIN
    -- Wait a bit for tables to be created by SQLAlchemy
    PERFORM pg_sleep(5);
    
    -- Check if sensor_readings table exists and create hypertable
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'sensor_readings') THEN
        PERFORM create_hypertable('sensor_readings', 'time', if_not_exists => TRUE);
    END IF;
END $$;