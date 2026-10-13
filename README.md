# Na7la Powerat 2.0 🐝⚡ (نحلة باورات) — Smart Power Strip Backend & Telegram Bot

> **Complete open-source cloud backend, modern web dashboard, and bilingual Telegram bot replacing the commercial "Voltra" app for the LG U+ / Jinheung MTTL-W01 4-outlet smart strip (المشترك الكوري).**

**English** | [العربية](README.ar.md) | [AGENTS.md (Knowledge Base)](AGENTS.md) | [Docs Directory](docs/)

---

## ⚡ What is Na7la Powerat?

**Na7la Powerat 2.0** (`na7la powerat` / نحلة باورات) transforms the smart power strip into a production-grade asynchronous cloud backend with multi-device management, bilingual Telegram bot control, recurring schedules, auto-off timers, live energy analytics with cost calculations in Egyptian Pounds (EGP), and hardware safety alarms.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                             NA7LA POWERAT 2.0 ECOSYSTEM                         │
├─────────────────────────┬───────────────────────────────┬───────────────────────┤
│    Telegram Bot         │        Web Dashboard          │      Android APK      │
│  (@Na7laPoweratBot)     │   http://<SERVER_IP>:8080     │   Built with Jetpack  │
│  Control from anywhere  │   Glassmorphic responsive UI  │   Compose Expressive  │
└────────────▲────────────┴───────────────▲───────────────┴───────────▲───────────┘
             │                            │                           │
             └────────────────────────────┼───────────────────────────┘
                                          │
                           ┌──────────────┴──────────────┐
                           │   FastAPI Async Backend     │
                           │   SQLite / PostgreSQL DB    │
                           │   Dual TCP Device Server    │
                           │   • TCP 10086 (FW 0.1.54)   │
                           │   • TCP 21197 (FW 0.1.55+)  │
                           └──────────────▲──────────────┘
                                          │ Raw TCP Protocol
                               ┌──────────┴──────────┐
                               │  LG U+ MTTL-W01     │
                               │  Korean Smart Strip │
                               └─────────────────────┘
```

---

## ✨ Features (Full Voltra Alternative)

1. **No Router Hacks or Port Forwarding at Home**: The strip initiates an outbound TCP socket to the server. Works across NAT, 4G, and dynamic home IPs without router DNS poisoning or DNAT.
2. **Dual-Port Support (All Firmware Revisions)**:
   - Port **`10086`**: Tested on firmware `0.1.54-1.0.66`.
   - Port **`21197`**: Tested on firmware `0.1.55-1.0.141` and `0.1.55-1.0.146`.
3. **Bilingual Telegram Bot (`@Na7laPoweratBot`)**:
   - Multi-device claiming via MAC address (`/start`).
   - 4 independent outlet toggle buttons with live power ratings.
   - Master switch (All ON / All OFF).
   - Custom outlet naming (e.g. "Router", "PC", "Charger").
   - Smart countdown timers (auto-off in 15m, 30m, 1h, 2h, etc.).
   - Daily scheduled automation routines (turn on/off at specific times).
   - Language selector (`English` / `العربية`).
4. **Energy Analytics & Cost Estimation (EGP)**:
   - Real-time active wattage (W) per outlet and total.
   - Cumulative energy consumption (kWh).
   - Cost tracking in Egyptian Pounds (EGP) based on residential electricity tariff tiers.
5. **Push Safety Alarms**:
   - Power outage & connection loss alerts.
   - Power restored alerts.
   - Overload warning (>3500W or >15.5A).
   - Overheat warning (>65°C).
6. **100% Backward Compatible**: Retains `/api/state` and `/api/onoff` endpoints for the native Android client APK.

---

## 🚀 Quick Start Guide

### 1. Requirements
* LG U+ / Jinheung **MTTL-W01** smart strip (stock firmware is fine).
* **2.4 GHz Wi-Fi** network (the strip does not support 5 GHz).
* A Linux VPS (e.g. AWS EC2, DigitalOcean, Hetzner) or a local machine that stays on.
* Python 3.10+.

### 2. Run the Server
```bash
# Clone the repository
git clone https://github.com/hassanaref/powerk.git
cd powerk

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run backend self-tests
python powerk.py selftest

# Start server
python powerk.py serve
```

### 3. Provision the Smart Strip (Once)
1. Hold the main button on the strip for **10 seconds** until the LED blinks rapidly.
2. Connect your laptop or phone to the Wi-Fi network `TONLY_TAP_XXXXXXX` (password: `LGU_XXXXXXX`).
3. Run the provisioning command:
   ```bash
   python powerk.py provision --ip <SERVER_PUBLIC_IP> --ssid "<WIFI_SSID>" --password "<WIFI_PASSWORD>"
   ```
4. **Crucial**: After the script prints `Done`, **unplug the strip from the wall for 20 seconds**, then plug it back in.
5. The LED will turn solid, and the strip will immediately connect to your server.

---

## 📚 Technical Documentation

Deep technical guides written for engineers and autonomous agents:

* 📖 **[AGENTS.md](AGENTS.md)**: Master knowledge base for AI coding agents and developers.
* 🔌 **[docs/HARDWARE_AND_PROTOCOL.md](docs/HARDWARE_AND_PROTOCOL.md)**: Reverse-engineered protocol specifications, frame structures, and regex patterns.
* 🛠️ **[docs/PROVISIONING_AND_TROUBLESHOOTING.md](docs/PROVISIONING_AND_TROUBLESHOOTING.md)**: Step-by-step pairing, Wi-Fi password special character pitfalls, and diagnostics.
* ☁️ **[docs/DEPLOYMENT_AND_ARCHITECTURE.md](docs/DEPLOYMENT_AND_ARCHITECTURE.md)**: AWS EC2 systemd service, firewall ports, and operations runbook.

---

## ⚖️ License & Attribution

Based on the original reverse-engineering work by Ahmed Tohamy (`ahmedtohamy1/powerk`).  
Extended into **Powerk 2.0** with asynchronous architecture, Voltra commercial features, and Telegram bot by Hassan Aref.
