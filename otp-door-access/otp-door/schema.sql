-- OTP Door Access: database schema (SQLite; also works on PostgreSQL with minor type changes)

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS devices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL UNIQUE,      -- e.g. "door-1" (hard-coded in the ESP32)
    api_key     TEXT NOT NULL,             -- secret the ESP32 sends with each request
    location    TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS otps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    device_id   TEXT NOT NULL REFERENCES devices(device_id),
    otp_hash    TEXT NOT NULL,             -- never store the OTP in plain text
    expires_at  TEXT NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0,
    attempts    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS access_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    user_id     INTEGER,
    result      TEXT NOT NULL,             -- GRANTED | DENIED | EXPIRED | USED | LOCKED
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_otps_device ON otps(device_id, used, expires_at);

-- Sample device (change the key!)
INSERT OR IGNORE INTO devices (device_id, api_key, location)
VALUES ('door-1', 'CHANGE_ME_DEVICE_KEY', 'Main door');
