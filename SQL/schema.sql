
CREATE DATABASE IF NOT EXISTS product_analytics_db;
USE product_analytics_db;

DROP TABLE IF EXISTS user_events;

CREATE TABLE user_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    event_date DATE NOT NULL,
    event_timestamp DATETIME NOT NULL,
    country VARCHAR(100),
    city VARCHAR(100),
    device_type VARCHAR(50),
    os VARCHAR(50),
    app_version VARCHAR(50),
    traffic_source VARCHAR(100),
    user_type VARCHAR(20),
    event_name VARCHAR(50) NOT NULL,
    session_duration INT DEFAULT 0,
    revenue DECIMAL(10, 2) DEFAULT 0.00,
    level_completed INT DEFAULT 0,
    purchase_amount DECIMAL(10, 2) DEFAULT 0.00,
    subscription VARCHAR(50),
    campaign VARCHAR(100),
    retention_day INT DEFAULT 0,
    INDEX idx_user_id (user_id),
    INDEX idx_event_date (event_date),
    INDEX idx_event_name (event_name),
    INDEX idx_country (country)
);