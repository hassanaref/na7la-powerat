# AGENTS.md — Na7la Powerat 2.0 (نحلة باورات) Knowledge Base & Agent Guide

> **Welcome, AI Agent or Developer!**  
> This file is the single source of truth for the **Na7la Powerat 2.0** (`na7la powerat` / نحلة باورات) ecosystem. It documents the reverse-engineered hardware protocols, network idiosyncrasies, firmware quirks, server architecture, and deployment procedures for the **LG U+ / Jinheung MTTL-W01** 4-outlet smart power strip (commonly known in Egypt and the Middle East as "المشترك الكوري" / The Korean Power Strip).

---

## 1. Project Mission & Context

### Why This Project Exists
Thousands of LG U+ / Jinheung smart power strips were imported into Egypt and other markets. Users originally had to rely on paid subscription apps (such as "Voltra") or complex Home Assistant / DNS redirection hacks.

**Na7la Powerat 2.0** provides a complete, free, self-hosted, cloud-capable Python backend and bilingual Telegram Bot (`@Na7laPoweratBot`) that:
1. **Replaces Voltra entirely**: 4-outlet independent relay control, custom naming, countdown auto-off timers, scheduled automation routines, power/energy monitoring, and Egyptian electricity tariff cost tracking (EGP).
2. **Requires zero router hacks**: No DNS poisoning, no NAT loopback, no firmware flashing. The strip dials out to the server via standard TCP.
3. **100% Backwards Compatible**: Maintains `/api/state` and `/api/onoff` endpoints for the native Android client APK (`android/`).

---

## 2. Hardware Specifications

| Attribute | Details |
|---|---|
| **Device Model** | LG U+ / Jinheung **MTTL-W01** (identified in protocol as `lgutap` or `LGU+-TAP-HW002`) |
| **Manufacturer** | Tonly Technology Co., Ltd. (OEM for LG U+ / TCL) |
| **SoC / Firmware** | Embedded Linux (BusyBox) running on a Tonly Wi-Fi chipset |
| **Relays** | 4 independently switched mechanical relays + 1 master cut-off |
| **Electrical Rating** | 16A, 250V~, 50/60 Hz (~3500W total maximum load) |
| **Sensors** | Individual power metering (mW) per outlet, cumulative energy (kWh), board temperature (°C), AC line voltage (mV) |
| **Wi-Fi Hardware** | **2.4 GHz only (802.11 b/g/n)**. *Does NOT support 5 GHz, WPA3-SAE, or PMF.* |
| **Setup Mode (SoftAP)** | SSID: `TONLY_TAP_XXXXXXX` \| Password: `LGU_XXXXXXX` (same 7 characters) |
| **Setup Port** | TCP `30300` (at `192.168.1.1` in SoftAP mode, or on local LAN) |
| **Outbound TCP Ports** | • Firmware `0.1.54`: TCP **`10086`**<br>• Firmware `0.1.55+` (`0.1.55-1.0.141`, `0.1.55-1.0.146`): TCP **`21197`** |

---

## 3. Protocol Specification (Reverse-Engineered)

All communication uses ASCII CRLF-terminated (`\r\n`) plain text strings over raw TCP sockets.

### 3.1 Provisioning Protocol (TCP 30300)
When the strip is in setup mode (SoftAP `192.168.1.1:30300`):

```
Client -> Strip: up:ip:<SERVER_IPV4>\r\n
Strip  -> Client: up:ip:ip_ok\r\n

Client -> Strip: up:connect:<SSID>:<PASSWORD>\r\n
Strip  -> Client: up:connect:connect_ok\r\n
```

### 3.2 Live Device Protocol (TCP 10086 & 21197)

#### Handshake / Boot Information (Inbound from Strip)
Sent immediately when the strip opens a TCP session to the server:
```
up:bootinfo:<MODEL>;<MAC>;<SERIAL>;<FW_VERSION>;connect\r\n
```
*Example:* `up:bootinfo:LGU+-TAP-HW002;2CE032C6E5E7;001122334455;0.1.55-1.0.146;connect`

#### Querying State (Outbound from Server)
To refresh all outlets, the server sends:
```
up:getinfo:all\r\n
```

#### Outlets State Telemetry (Inbound from Strip)
The strip replies with 5 colon-separated segments (outlets 1 to 4, plus index 5 as master total):
```
up:getinfo:<tag1>:<tag2>:<tag3>:<tag4>:<tag5>\r\n
```
Each segment is semicolon-separated:
`ch:power_mw;state;on_flag;0;0;power_mw;energy_hex;00000000;00000000;0;00;temp_c`
* `channel`: `1` to `4` (or `5` for master)
* `state`: `"on"` or `"off"`
* `power_mw`: Active power in milliwatts (`12500` = 12.5 W)
* `energy_hex`: Cumulative energy in hex (`0000000A` = 10 Wh = 0.01 kWh)
* `temp_c`: Internal thermistor temperature in Celsius (`26` = 26°C)

#### Line Voltage Telemetry (Inbound from Strip)
Sent periodically by the strip:
```
up:power_report:1:<VOLTAGE_MV>\r\n
```
*Example:* `up:power_report:1:230200` represents 230.2 Volts.

#### Wi-Fi Signal Telemetry (Query / Response)
Server sends:
```
up:query:wifirssi\r\n
```
Strip replies:
```
up:query:<RSSI_DBM>\r\n
```
*Example:* `up:query:-43` represents -43 dBm (strong signal).

#### Relay Switching (Outbound from Server)
To toggle a specific relay:
```
up:onoff:<CHANNEL>:<on|off>\r\n
```
*Example:* `up:onoff:1:on` turns outlet 1 ON.
The strip replies: `up:onoff:<CHANNEL>:<on|off>` or `up:onoff:ack`.

#### Hardware Button Push (Inbound from Strip)
When a human presses a physical button on the strip:
```
up:event:onoff:<CHANNEL>:<on|off>\r\n
```
Channel `0` indicates the master power switch (all outlets). Channels `1`–`4` indicate individual outlets.

---

## 4. Critical Hardware & Network Gotchas (DO NOT MISS)

### ⚠️ Gotcha 1: The Wi-Fi Password Special Characters Trap
The internal Linux SoC uses a simple shell script (`sed` / `wpa_cli`) to write network credentials to `/etc/wpa_supplicant.conf`.
* Characters like `/` break the `sed` delimiter.
* Characters like `*` expand to filesystem wildcards.
* **If the Wi-Fi password contains `*`, `/`, or `:`, the strip will corrupt its config and blink slowly forever.**
* **Fix**: Use only letters and digits for IoT Wi-Fi networks (e.g. `iot_wifi` / `Password1234`), or use a dedicated router Guest Network without special characters.

### ⚠️ Gotcha 2: Firmware Port Differences (10086 vs 21197)
* Older firmware (`0.1.54-1.0.66`) hardcodes TCP **`10086`**.
* Newer firmware (`0.1.55-1.0.141`, `0.1.55-1.0.146`) hardcodes TCP **`21197`**.
* **Fix**: The Powerk backend binds listeners to **both ports simultaneously** in `app/device_server/server.py`. Both ports must be open in the AWS Security Group.

### ⚠️ Gotcha 3: The 20-Second Post-Provision Power Cycle
After running `python powerk.py provision` and receiving `up:connect:connect_ok`, the strip stores the settings in flash memory but its network stack often stays partially uninitialized until hard rebooted.
* **Fix**: Always unplug the strip from the 220V wall outlet for **20–30 seconds** (draining internal capacitors), then plug it back in. It will boot cleanly, join the Wi-Fi, and dial the server.

### ⚠️ Gotcha 4: 2.4 GHz Only & 5GHz Band Steering
The Tonly Wi-Fi chip only supports 802.11 b/g/n on 2.4 GHz.
* If your home router uses band steering (combining 2.4 GHz and 5 GHz under one SSID) or enforces WPA3, the strip will fail to associate.
* Create a dedicated 2.4 GHz SSID (or 2.4 GHz Guest Network) with WPA/WPA2-PSK Personal.

### ⚠️ Gotcha 5: MAC Address Formatting
Users supply MAC addresses in various formats:
* Plain hex: `2CE032C6E5E7`
* Colon-separated: `2C:E0:32:C6:E5:E7`
* Cisco dot notation: `2CE0.32C6.E5E7`
* Always sanitize MAC strings with: `re.sub(r"[^0-9A-Fa-f]", "", text).upper()`.

### ⚠️ Gotcha 6: SQLAlchemy 2.0 Async Greenlet Context
Never access lazy relationships outside an active DB session.
* All ORM models (`User`, `Device`, `Outlet`, `Schedule`, `Telemetry`) in `app/models/__init__.py` must use `lazy="selectin"`.
* When rendering bot keyboards or API snapshots when a device is offline, use `make_device_snapshot()` to safely build dictionary structures without triggering detached instance errors.

---

## 5. Software Architecture

```
                      ┌──────────────────────────────────────────────┐
                      │                Powerk 2.0                    │
                      │                                              │
                      │  FastAPI Web Dashboard (Port 8080)           │
                      │  REST API (/api/v1/*, /api/state, /api/onoff)│
                      │  Telegram Bot (@Na7laPoweratBot)             │
                      │  Background Schedulers & Energy Analytics    │
                      └──────▲─────────────────▲─────────────────────┘
                             │                 │
              TCP Port 10086 │                 │ TCP Port 21197
              (FW 0.1.54)    │                 │ (FW 0.1.55+)
                             │                 │
                      ┌──────┴─────────────────┴──────┐
                      │    LG U+ MTTL-W01 Power Strip │
                      │       MAC: 2CE032C6E5E7       │
                      └───────────────────────────────┘
```

### Directory Structure
* `powerk.py` / `na7la.py`: CLI entry point (`serve`, `provision`, `selftest`).
* `app/config.py`: Pydantic settings loading from `.env` or system environment.
* `app/database.py`: Async SQLite engine with `aiosqlite` and dynamic column migration.
* `app/models/`: SQLAlchemy 2.0 data models (`User`, `Device`, `Outlet`, `Schedule`, `DeviceShare`, `Scene`).
* `app/device_server/`:
  * `protocol.py`: Regex parsers and command formatters for the `up:...` protocol.
  * `session.py`: Asynchronous TCP socket connection manager with command locks and current calibration.
  * `hub.py`: Central device singleton registry, event emitter, and protection hooks.
  * `server.py`: Async TCP servers binding ports 10086 and 21197 concurrently.
* `app/bot/`:
  * `bot.py`: Telegram application runner with long polling.
  * `handlers.py`: Bilingual message and callback handlers (`/start`, `/en`, `/ar`, claiming, control).
  * `keyboards.py`: Interactive inline keyboard builders.
* `app/services/`:
  * `auth_service.py`: User token generation, validation, and multi-tenant device access verification (`verify_device_access`).
  * `protection_service.py`: Autonomous hardware protection engine (current calibration, voltage guard, overload trip, cold boot surge router priority, child lock reversal, standby cutoffs).
  * `device_service.py`: Device claiming, pre-registration, outlet renaming.
  * `scheduler_service.py`: Auto-off countdowns and recurring schedules loop.
  * `energy_service.py`: kWh tracking and Egyptian electricity cost calculations (EGP).
  * `alert_service.py`: Telegram push notifications on state anomalies (overheat, overload, disconnect).
* `app/api/`:
  * `v1/auth.py`: User signup, login, profile (`/me`), and strip claiming.
  * `v1/devices.py`: User-scoped strip queries and protection settings (`/protection`).
  * `v1/outlets.py`: Outlet toggle, rename, and smart configuration (`/smart`).
  * `v1/schedules.py`: Active schedule management and countdown timers.
  * `v1/stats.py`: Real-time energy analytics and cost breakdown.
  * `legacy.py`: Scoped backwards-compatibility routes (`/api/state`, `/api/onoff`, `/na7la_powerat.apk`).
* `android/`:
  * `app/src/main/java/com/powerk/app/`:
    * `Provisioning.kt`: In-app direct TCP socket wizard connecting to `192.168.1.1:30300`.
    * `Security.kt`: Biometric fingerprint/face prompt and 4-digit PIN lock gate.
    * `Server.kt`: User profile, token, server address, and preferences persistence.
    * `Api.kt`: Scoped REST client handling auth, protection, telemetry, and control.
    * `Ui.kt`: 4-tab Jetpack Compose Material 3 interface (Plugs, Protection, Setup, Settings).

---

## 6. Multi-Tenancy & Data Isolation Model

> **Core Rule**: Users must NEVER see or control other users' smart strips.

1. **User Token Auth**: Every user is assigned a 64-character hex `user_token`. Requests must provide this token via `X-User-Token`, `Authorization: Bearer <token>`, or `?user_token=`.
2. **Device Claiming**: Physical strips are claimed by MAC address. If User A has claimed a device, User B's attempt to claim it is rejected with `403 Forbidden: Device is already linked to another user account`.
3. **Scoped Responses**:
   * `GET /api/state` and `GET /api/v1/devices` inspect the caller's token and return **only** strips where `owner_telegram_id == user.telegram_id` or user has a granted `DeviceShare`.
   * `POST /api/onoff` and `POST /api/v1/outlets/toggle` strictly check ownership via `AuthService.verify_device_access`. Unauthorized callers receive `403 Forbidden`.
4. **Admin Bypass**: The server master token `settings.API_TOKEN` grants superuser admin access for maintenance.

---

## 7. Autonomous Hardware Protection Engine

The `ProtectionService` runs 24/7 on the server, enforcing hardware rules even when the phone or app is disconnected:
1. **Current Calibration**: Raw telemetry noise offset is subtracted: $\max(0.0, I_{\text{raw}} - 0.019\text{ A})$.
2. **Over/Under Voltage Guard**: Default safe window $190\text{--}245\text{ V}$. If line voltage exceeds bounds, all relays are immediately tripped OFF and a Telegram alert is dispatched.
3. **Overload Cutoff**: Trips all relays if combined active load exceeds $3200\text{ W}$.
4. **Surge & Cold Boot Delay**: Upon AC power restoration after a blackout, router outlet (Channel 1) turns ON immediately to establish Wi-Fi, while sensitive electronics remain OFF or delayed.
5. **Child Lock (قفل الأطفال)**: Reverses hardware button presses on the physical strip (`up:event:onoff`) so relays can only be toggled via software.
6. **Auto-Off & Standby Cutoffs**: Background loop turns off outlets after configured timer durations or when connected devices enter low-wattage standby below the threshold.

---

## 8. Android App Overhaul & APK Compilation Runbook

### Direct In-App TCP Provisioning
* Connects directly to `192.168.1.1:30300` in SoftAP mode.
* Validates credentials, strictly disallowing `*`, `/`, or `:` (preventing Linux `sed` configuration corruption).
* Dispatches `up:ip:<SERVER_IP>\r\n` and `up:connect:<SSID>:<PASS>\r\n`.
* Prompts the user with a 25-second power-cycle countdown timer to discharge capacitors before reboot.

### How to Compile the Android APK
Prerequisites:
* **JDK 17**: Microsoft OpenJDK 17 (`C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot`).
* **Android SDK**: Android Platform 37 (`cmdline-tools\latest`).

Build Command:
```powershell
$env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot"
$env:ANDROID_HOME = "C:\Users\hassa\AppData\Local\Android\Sdk"
$env:Path = "$env:JAVA_HOME\bin;" + $env:Path
cd android
.\gradlew assembleDebug
```
Output path: `android/app/build/outputs/apk/debug/app-debug.apk` (~20.3 MB).

### Direct Download URL from Production Server
The AWS EC2 backend serves the compiled APK at:
* **Direct Download**: `http://13.61.25.9:8080/na7la_powerat.apk`

---

## 9. Production Deployment Runbook (AWS EC2)

### Server Details
* **Host**: Ubuntu 24.04 LTS (`ubuntu@13.61.25.9`)
* **Python**: Python 3.12+ in `/home/ubuntu/powerk/venv`
* **Systemd Service**: `/etc/systemd/system/powerk.service`

### Essential Commands
```bash
# Check service status
sudo systemctl status powerk

# View live application logs
sudo journalctl -u powerk -f --no-pager

# Restart service after code changes
sudo systemctl restart powerk

# Verify open ports
sudo ss -tulpn | grep -E '8080|10086|21197'

# Sniff strip packets live
sudo tcpdump -i any -n "port 10086 or port 21197"
```

### Required AWS Security Group Inbound Rules
* **Port 22 (SSH)**: Admin access.
* **Port 8080 (HTTP)**: Web dashboard, REST API, and APK downloads.
* **Port 10086 (TCP)**: Strip device communication (FW 0.1.54).
* **Port 21197 (TCP)**: Strip device communication (FW 0.1.55+).

---

## 10. Adding Features or Debugging for Future Agents
1. **Always run selftest**: Run `python powerk.py selftest` before making commits. It validates protocol regex parsers, database migrations, scheduler creation, and energy calculators without requiring a physical device.
2. **Never break legacy API**: The native Android application relies on `GET /api/state` and `POST /api/onoff`. Keep these endpoints intact in `app/api/legacy.py` while respecting user tokens.
3. **Avoid Telegram 409 Conflict**: Only run one instance of the bot application at a time. The systemd service on EC2 is the production polling instance.

