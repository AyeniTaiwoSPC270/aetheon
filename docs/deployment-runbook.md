# Deployment Runbook — Oracle Cloud Always Free

Provisioning steps for running the Aethon wrapper daemon unattended.
Follow these once you have an Oracle Cloud account and have created an
Always Free compute instance (Ubuntu recommended).

## 1. Provision the instance

Create an Always Free VM.Standard.E2.1.Micro (or A1.Flex within the
Always Free allowance) instance via the Oracle Cloud console. Note its
public IP and download the SSH key pair Oracle generates.

## 2. SSH in and install dependencies

```bash
ssh -i <your-key.pem> ubuntu@<instance-ip>

# Node.js (for InkOS) + npm
sudo apt update
sudo apt install -y nodejs npm git
npm i -g @actalk/inkos

# uv (Python package manager this project uses)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

Verify: `node --version`, `npm --version`, `uv --version`, `inkos --version`.

## 3. Clone the repository

Requires the GitHub remote to exist first (a separate, explicitly
confirmed step — see the daemon design spec, Decision 7).

```bash
git clone <github-remote-url> aethon
cd aethon
uv sync
```

## 4. Configure secrets

Create `.env` directly on the VM over this SSH session — never paste real
key values through a chat assistant:

```bash
cat > .env <<'EOF'
GEMINI_API_KEY=<your key>
TELEGRAM_BOT_TOKEN=<your bot token>
TELEGRAM_CHAT_ID=<your chat id>
EOF
chmod 600 .env
```

## 5. Verify one manual run

```bash
set -a && source .env && set +a
uv run python -m src.wrapper.run --once
```

Confirm a Telegram message arrives (either a morning card or a halt
notice) before relying on cron.

## 6. Schedule it

```bash
chmod +x scripts/cron-run.sh
crontab -e
```

Add (adjust the hour to your preferred local time on the VM — check
`timedatectl` for the VM's timezone):

```
0 3 * * * /home/ubuntu/aethon/scripts/cron-run.sh
```

## 7. Troubleshooting

- `sandbox/cron.log` — raw stdout/stderr from each cron invocation,
  including anything that failed before the wrapper's own logging
  started.
- `sandbox/wrapper_run.log` — structured JSON-lines events from
  `run_once()` itself (halt reasons, check verdicts, delivery outcomes).
- No Telegram message arrived: check `.env` is readable (`chmod 600`,
  owned by the right user), and re-run step 5 manually to see the
  actual error.
