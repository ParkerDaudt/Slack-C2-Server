# C2 Server with Slack Integration

## Purpose

This project provides a simple Command & Control (C2) framework written in Python that uses Slack for command input and output. It allows cybersecurity professionals to issue shell commands, transfer files, and establish an interactive shell on one or more agents, with all results delivered to a designated Slack channel.

## Summary

* **Server** (`server.py`): A Flask-based C2 server that:

  * Receives slash-command requests from Slack and queues them for agents
  * Exposes `/agent/poll` and `/agent/report` endpoints over HTTPS (tunneled via ngrok or hosted on a domain)
  * Persists commands and registration data in SQLite (`c2.db`)
  * Optionally tracks agent registrations and can alert on failures

* **Agent** (`agent.py`): A Python script that:

  * Generates a unique, persistent `agent_id` on first run
  * Registers itself with the C2 server and notifies Slack when it comes online
  * Polls `/agent/poll` at regular intervals for new commands
  * Executes shell commands, handles file transfers (`get <path>`), and interactive shell sessions
  * Reports results (stdout, stderr, exit codes) back to `/agent/report`

## Requirements

* Python 3.8 or higher
* Flask
* APScheduler
* python-dotenv
* requests
* sqlite3 (standard library)

## Installation

```bash
# Clone the repository
git clone https://github.com/ParkerDaudt/Slack-C2-Server.git
cd c2-server

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
# .\venv\Scripts\Activate.ps1  # Windows PowerShell

# Install dependencies
pip install -r requirements.txt
```

## Configuration

1. Copy the provided `.env.example` to `.env` and fill in your values:

   ```ini
   FLASK_APP=server.py
   FLASK_ENV=production

   # C2 Server
   SERVER_URL=https://<your-domain-or-ngrok-url>
   AGENT_TOKEN=<your-shared-secret>

   # Slack
   SLACK_SIGNING_SECRET=<your-slack-signing-secret>
   SLACK_WEBHOOK_OUTPUT=<incoming-webhook-for-results>
   SLACK_WEBHOOK_ALERTS=<incoming-webhook-for-alerts-or-reuse-output>
   SLACK_WEBHOOK_AGENT_ONLINE=<incoming-webhook-for-online-notifications>

   # Agent Settings
   POLL_INTERVAL=30         # seconds
   RETRY_ATTEMPTS=3
   RETRY_INTERVAL=10        # seconds
   HEARTBEAT_TIMEOUT=60     # seconds (if using heartbeat logic)
   AGENT_ID_FILE=agent_id.txt
   ```
2. Initialize the database (tables are auto-created on server startup).

## Usage

### Start the C2 Server

```bash
# From project root
flask run --host=0.0.0.0 --port=5000
```

Or:

```bash
python server.py
```

### Expose to Slack (for development)

```bash
ngrok http 5000
# Copy the HTTPS forwarding URL and update SERVER_URL and Slash Command Request URL
```

### Start an Agent

```bash
python agent.py
```

### Issue Commands via Slack

1. In your Slack workspace, in the selected “command” channel, type:

   ```text
   /c2 <agent_id> <shell_command>
   ```

   Example:

   ```text
   /c2 host-01 whoami
   ```
2. You will receive an immediate ack:

   > Command queued for `host-01`
3. Within `POLL_INTERVAL` seconds, command output appears in your output channel:

   ```
   parker\@host-01
   ```

### File Transfer

To retrieve a file:

```text
/c2 host-01 get /path/to/file.txt
```

The agent will base64-encode and send back:

```
FILE:/path/to/file.txt:PGZpcnN0LWxpbmU+CmZpcnN0IGxpbmUgdGV4dAo=
```

### Interactive Shell

Start a shell session:

```text
/c2 host-01 shell
```

Then follow prompts in your agent console.

## Troubleshooting

* **`dispatch_failed` in Slack**: Ensure your Slash Command Request URL (including `/slack/command`) matches your exposed HTTPS endpoint exactly and your Slack Signing Secret is correct.
* **Agent 401 Unauthorized**: Confirm `AGENT_TOKEN` matches in both server and `.env` for the agent, and that it’s passed in `X-Agent-Token` header.
* **Agent offline alerts**: If using heartbeat logic, ensure the agent polls immediately on startup or remove the heartbeat scheduler as needed.
* **ModuleNotFoundError**: Activate your virtualenv and run `pip install -r requirements.txt`.

## License

This project is released under the MIT License. Feel free to adapt and extend as needed.
