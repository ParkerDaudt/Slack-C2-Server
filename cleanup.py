import sqlite3

DB = 'c2.db'
OLD_ID = 'host-01'   # change this if needed

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Delete all queued/processed commands for that agent
cur.execute("DELETE FROM commands WHERE agent_id = ?", (OLD_ID,))

# If you have an agents table (from registration), delete that too
cur.execute("DELETE FROM agents WHERE agent_id = ?", (OLD_ID,))

# If you still have a heartbeats table, you can clean it as well
cur.execute("DELETE FROM heartbeats WHERE agent_id = ?", (OLD_ID,))

conn.commit()
conn.close()

print(f"Removed all data for agent_id = '{OLD_ID}'")
