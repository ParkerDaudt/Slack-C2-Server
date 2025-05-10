-- schema.sql
CREATE TABLE IF NOT EXISTS commands (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT,
  payload TEXT,
  status TEXT,         -- pending, done, failed
  result TEXT,
  retries INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS heartbeats (
  agent_id TEXT PRIMARY KEY,
  last_seen DATETIME
);
