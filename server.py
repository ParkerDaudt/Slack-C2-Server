import os, hmac, hashlib, sqlite3, json
from time import time
from datetime import datetime
from flask import Flask, request, make_response
from apscheduler.schedulers.background import BackgroundScheduler
import requests

# Load env
from dotenv import load_dotenv
load_dotenv()
print("➤ Loaded SLACK_SIGNING_SECRET:", repr(os.environ.get("SLACK_SIGNING_SECRET")))


HEARTBEAT_TIMEOUT = int(os.environ.get('HEARTBEAT_TIMEOUT', '60'))

app = Flask(__name__)
DB_PATH = 'c2.db'

#####################
# Helpers
#####################

def slack_command():
    print("→ /slack/command called:", request.form)

def db_connect():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute('''
      CREATE TABLE IF NOT EXISTS commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT,
        payload TEXT,
        status TEXT,
        result TEXT,
        retries INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    ''')
    cur.execute('''
      CREATE TABLE IF NOT EXISTS heartbeats (
        agent_id TEXT PRIMARY KEY,
        last_seen DATETIME
      )
    ''')
    cur.execute("""
    CREATE TABLE IF NOT EXISTS agents (
  agent_id TEXT PRIMARY KEY,
  registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
  """)
    conn.commit()
    conn.close()

# Call it right after you define db_connect():
init_db()

def verify_slack(req):
    timestamp = req.headers.get('X-Slack-Request-Timestamp', '')
    slack_sig = req.headers.get('X-Slack-Signature', '')
    body = req.get_data().decode('utf-8')
    basestring = f"v0:{timestamp}:{body}"
    my_sig = 'v0=' + hmac.new(
        os.environ['SLACK_SIGNING_SECRET'].encode('utf-8'),
        basestring.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    print("» Slack timestamp:", timestamp)
    print("» Slack signature header:", slack_sig)
    print("» Computed signature   :", my_sig)
    print("» Basestring to hash   :", basestring)

    return hmac.compare_digest(my_sig, slack_sig)

def db_connect():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

#####################
# Slash Command Endpoint
#####################
@app.route('/slack/command', methods=['POST'])
def slack_command():
    if not verify_slack(request):
        return make_response("Invalid signature", 403)

    data = request.form
    agent_id = data.get('text').split()[0]  # first word = agent ID
    cmd = ' '.join(data.get('text').split()[1:])
    conn = db_connect()
    conn.execute(
      "INSERT INTO commands(agent_id,payload,status) VALUES(?,?,?)",
      (agent_id, cmd, 'pending')
    )
    conn.commit()
    conn.close()
    return make_response(f"Command queued for `{agent_id}`", 200)

#####################
# Agent Polling
#####################
@app.route('/agent/poll', methods=['POST'])
def agent_poll():
    token = request.headers.get('X-Agent-Token')
    if token != os.environ['AGENT_TOKEN']:
        return make_response("Unauthorized", 401)

    data = request.get_json()
    agent_id = data['agent_id']
    # update heartbeat
    conn = db_connect()
    conn.execute(
      "REPLACE INTO heartbeats(agent_id,last_seen) VALUES(?,?)",
      (agent_id, datetime.utcnow())
    )
    # fetch next command
    cur = conn.execute(
      "SELECT id,payload FROM commands WHERE agent_id=? AND status='pending' ORDER BY id LIMIT 1",
      (agent_id,)
    )
    row = cur.fetchone()
    if row:
        cmd_id, payload = row
        conn.execute("UPDATE commands SET status='in-progress' WHERE id=?", (cmd_id,))
        conn.commit()
        conn.close()
        return {'cmd_id': cmd_id, 'payload': payload}
    conn.close()
    return {'cmd_id': None, 'payload': None}

#####################
# Agent Reporting
#####################
@app.route('/agent/report', methods=['POST'])
def agent_report():
    token = request.headers.get('X-Agent-Token')
    if token != os.environ['AGENT_TOKEN']:
        return make_response("Unauthorized", 401)

    data = request.get_json()
    cmd_id = data['cmd_id']
    exit_code = data['exit_code']
    output = data['output']
    conn = db_connect()
    status = 'done' if exit_code == 0 else 'failed'
    conn.execute(
      "UPDATE commands SET status=?, result=?, retries=retries+1 WHERE id=?",
      (status, output, cmd_id)
    )
    conn.commit()
    conn.close()

    # Post result to Slack
    webhook = (
      os.environ['SLACK_WEBHOOK_OUTPUT']
      if exit_code == 0
      else os.environ.get('SLACK_WEBHOOK_ALERTS', os.environ['SLACK_WEBHOOK_OUTPUT'])
    )
    text = f"```{output}```" if len(output) < 3000 else None
    payload = {'text': text or f"Result too long; see attached."}
    if len(output) >= 3000:
      payload['attachments'] = [{
        'text': output[:3000] + '...'
      }]
    requests.post(webhook, json=payload)
    return {'status': 'ok'}

@app.route('/agent/register', methods=['POST'])
def agent_register():
    # Log for debugging
    print("→ /agent/register ping:", request.headers.get('X-Agent-Token'), request.get_json())

    token = request.headers.get('X-Agent-Token')
    if token != os.environ['AGENT_TOKEN']:
        return make_response("Unauthorized", 401)

    data = request.get_json()
    agent_id = data.get('agent_id')
    if not agent_id:
        return make_response("Bad Request: missing agent_id", 400)

    conn = db_connect()
    # optional: create an `agents` table to track registrations
    conn.execute(
      "INSERT OR IGNORE INTO agents(agent_id, registered_at) VALUES(?, CURRENT_TIMESTAMP)",
      (agent_id,)
    )
    conn.commit()
    conn.close()

    return {"status": "registered"}, 200

#####################
# Background Jobs
#####################
def check_heartbeats():
    conn = db_connect()
    timeout = int(os.environ['HEARTBEAT_TIMEOUT'])
    cutoff = datetime.utcnow().timestamp() - timeout
    for agent_id, last_seen in conn.execute("SELECT agent_id, last_seen FROM heartbeats"):
        if datetime.fromisoformat(last_seen).timestamp() < cutoff:
            requests.post(os.environ['SLACK_WEBHOOK_ALERTS'],
                          json={'text': f":rotating_light: Agent `{agent_id}` offline"})
    conn.close()

scheduler = BackgroundScheduler()
scheduler.add_job(check_heartbeats, 'interval', seconds=HEARTBEAT_TIMEOUT)
scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
