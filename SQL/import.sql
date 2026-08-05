-- Data Import Script (MySQL / PostgreSQL compatible format)
-- Ensure local infile is enabled or use bulk copy tool
LOAD DATA INFILE '/path/to/Dataset/user_events.csv'
INTO TABLE user_events
FIELDS TERMINATED BY ',' 
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(user_id, session_id, event_date, event_timestamp, country, city, device_type, os, app_version, traffic_source, user_type, event_name, session_duration, revenue, level_completed, purchase_amount, subscription, campaign, retention_day);