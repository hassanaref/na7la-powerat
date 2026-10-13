# Deployment & Architecture Guide

This document details the production architecture and operational runbook for running Powerk on AWS EC2 or any Linux VPS.

---

## 1. System Architecture

```
                  Internet / Telegram Cloud
                              │
                    HTTPS (Long Polling)
                              │
  ┌───────────────────────────▼───────────────────────────┐
  │                   AWS EC2 Instance                    │
  │                  IP: 13.61.25.9                       │
  │                                                       │
  │  ┌─────────────────────────────────────────────────┐  │
  │  │                 Powerk Backend                  │  │
  │  │                                                 │  │
  │  │  • FastAPI Web Server (:8080)                   │  │
  │  │     - Web Dashboard & Swagger UI                │  │
  │  │     - User Token Auth & Multi-Tenancy Scoping   │  │
  │  │     - Android APK Delivery (/na7la_powerat.apk) │  │
  │  │  • Telegram Bot Poller (@Na7laPoweratBot)       │  │
  │  │  • Autonomous Hardware Protection Engine        │  │
  │  │  • Scheduler & Energy Analytics Engine          │  │
  │  │  • SQLite DB (powerk.db via Async SQLAlchemy)   │  │
  │  │                                                 │  │
  │  │  • Async TCP Device Server Listeners:           │  │
  │  │     - Port 10086 (FW 0.1.54)                    │  │
  │  │     - Port 21197 (FW 0.1.55+)                   │  │
  │  └────────▲────────────────────────────▲───────────┘  │
  └───────────┼────────────────────────────┼──────────────┘
              │ TCP 10086                  │ TCP 21197
              │                            │
      ┌───────┴──────┐              ┌──────┴──────┐
      │  Older MTTL  │              │  Newer MTTL │
      │ Smart Strip  │              │ Smart Strip │
      └──────────────┘              └─────────────┘
```

---

## 2. Server Prerequisites

* **Operating System**: Ubuntu 22.04 LTS or 24.04 LTS (x86_64 or ARM64).
* **Python**: Python 3.10 or higher.
* **Firewall / AWS Security Groups**:
  * TCP `22` (SSH management)
  * TCP `8080` (Web UI & REST API)
  * TCP `10086` (Legacy firmware smart strips)
  * TCP `21197` (Modern firmware smart strips)

---

## 3. Installation Steps

### Step 1: Clone Repository & Virtual Environment
```bash
sudo apt update && sudo apt install -y python3 python3-venv git
git clone https://github.com/hassanaref/powerk.git /home/ubuntu/powerk
cd /home/ubuntu/powerk

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Environment Configuration
Create `/home/ubuntu/powerk/.env`:
```ini
DEVICE_PORT=10086
WEB_PORT=8080
HOST=0.0.0.0

# Database
DATABASE_URL=sqlite+aiosqlite:///powerk.db

# Telegram Bot
TELEGRAM_BOT_TOKEN=8873309591:AAHgiKUL4cvoDsCLGKMPMKS7rNcKEt7XdSI
TELEGRAM_ENABLED=true

# Intervals (Seconds)
POLL_INTERVAL=5.0
DIAGNOSTICS_INTERVAL=15.0
TELEMETRY_LOG_INTERVAL=60.0

# Electricity Tariff
ELECTRICITY_COST_PER_KWH=1.85
```

### Step 3: Run Self-Tests
Verify the environment before starting services:
```bash
python powerk.py selftest
```

---

## 4. Systemd Service Configuration

Create `/etc/systemd/system/powerk.service`:
```ini
[Unit]
Description=Powerk Smart Strip Backend & Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/powerk
ExecStart=/home/ubuntu/powerk/venv/bin/python powerk.py serve
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable powerk
sudo systemctl start powerk
```

---

## 5. Operations & Diagnostics

### Viewing Logs
```bash
# Real-time tailing of application logs
sudo journalctl -u powerk -f --no-pager

# Last 50 log lines
sudo journalctl -u powerk -n 50 --no-pager
```

### Verifying Listening Ports
```bash
sudo ss -tulpn | grep -E '8080|10086|21197'
```
Expected output:
* `0.0.0.0:8080` (FastAPI HTTP)
* `0.0.0.0:10086` (TCP Device Listener 1)
* `0.0.0.0:21197` (TCP Device Listener 2)

### Inspecting Live State via REST
```bash
# Current devices
curl -s http://localhost:8080/api/v1/devices | jq .

# Legacy Android app format
curl -s http://localhost:8080/api/state | jq .
```
