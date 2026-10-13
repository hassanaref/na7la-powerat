# Hardware & Network Protocol Specification

> **Device:** LG U+ / Jinheung Smart Multi-tap (Model: `MTTL-W01` / `lgutap`)  
> **Manufacturer:** Tonly Technology Co., Ltd.  
> **Firmware Versions:** `0.1.54-1.0.66`, `0.1.55-1.0.141`, `0.1.55-1.0.146`

---

## 1. Physical Device & Indicators

### Relays & Switches
- **Master Switch**: Physical push button on top toggles all 4 outlets simultaneously.
- **Individual Buttons**: 4 mechanical buttons correspond to outlets 1 through 4.
- **Relay Mechanism**: 4 internal mechanical latching/non-latching relays rated for 16A total resistive load at 250V AC.

### LED Indicator States
- **Rapid Blinking (~5-10 Hz)**: Setup Mode (SoftAP). The strip is broadcasting `TONLY_TAP_XXXXXXX` and listening on TCP `30300` at `192.168.1.1`.
- **Slow Blinking (~1 Hz)**: Station Connecting Mode. The strip is attempting to associate with the Wi-Fi AP or waiting for an IP via DHCP, or connecting to the cloud server TCP socket.
- **Solid Continuous Light**: Operational Mode. The strip has successfully connected to Wi-Fi and established an active TCP socket session with the server.

---

## 2. Setup & Provisioning Protocol (TCP 30300)

When the main button is held for ~10 seconds, the strip starts an open Wi-Fi network:
* **SSID**: `TONLY_TAP_<MAC_LAST_7>` (e.g. `TONLY_TAP_2C6E5E7`)
* **Password**: `LGU_<MAC_LAST_7>` (e.g. `LGU_2C6E5E7`)
* **Internal IP**: `192.168.1.1`
* **Setup Service**: TCP port `30300`

The client connects to `192.168.1.1:30300` and sends CRLF-terminated lines:

### Command 1: Configure Server IPv4
```text
up:ip:13.61.25.9\r\n
```
**Expected Response:**
```text
up:ip:ip_ok\r\n
```

### Command 2: Configure Wi-Fi Credentials
```text
up:connect:my_wifi_ssid:my_wifi_password\r\n
```
**Expected Response:**
```text
up:connect:connect_ok\r\n
```

> **Important Notes on Setup Protocol:**
> 1. Neither the SSID nor the password can contain the colon `:` delimiter or newline characters.
> 2. The password should not contain `/` or `*` due to embedded shell script limitations.
> 3. After receiving `connect_ok`, the strip saves both values to NVRAM and restarts its network stack.

---

## 3. Operational Protocol (TCP 10086 & 21197)

### Inbound Initial Handshake (`bootinfo`)
Immediately upon connecting to the server's TCP socket, the strip sends:
```text
up:bootinfo:<model>;<mac>;<serial>;<firmware>;connect\r\n
```
**Example:**
```text
up:bootinfo:LGU+-TAP-HW002;2CE032C6E5E7;001122334455;0.1.55-1.0.146;connect
```

**Regex:**
```python
BOOTINFO_RE = re.compile(r"^up:bootinfo:([^;]+);([0-9a-fA-F]{12});([^;]+);([^;]+);connect$")
```

### Refresh Query (`getinfo`)
To request full telemetry from all outlets, the server sends:
```text
up:getinfo:all\r\n
```

The strip replies with a multi-segment line:
```text
up:getinfo:1:100;on;1;0;0;12500;0000000A;00000000;00000000;0;00;31:2:200;off;0;0;0;0;00000005;00000000;00000000;0;00;32:3:300;on;1;0;0;45000;0000000C;00000000;00000000;0;00;33:4:400;off;0;0;0;0;00000002;00000000;00000000;0;00;34:5:1000;on;1;0;0;57500;00000023;00000000;00000000;0;00;34\r\n
```

**Parsing Rules per Outlet:**
Each segment has the form:
`{channel}:{relay_id};{state_str};{is_on};0;0;{power_mw};{energy_hex};00000000;00000000;0;00;{temp_c}`
* `channel`: Outlet number (`1`, `2`, `3`, `4`). Segment `5` is aggregate total.
* `state_str`: `"on"` or `"off"`.
* `is_on`: `1` if relay is energized, `0` if open.
* `power_mw`: Active power in milliwatts (`12500` / 1000 = `12.5 W`).
* `energy_hex`: Cumulative watt-hours in hexadecimal string (`0000000A` hex = `10 Wh` = `0.01 kWh`).
* `temp_c`: Temperature in degrees Celsius (`31` = 31°C).

### Line Voltage Reporting (`power_report`)
The strip periodically sends voltage reports:
```text
up:power_report:1:230200\r\n
```
* Channel `1` provides AC line voltage in millivolts.
* Value `230200` = `230.2 V`.
* Any value `< 50000` (50V) is treated as an invalid or uncalibrated reading.

**Regex:**
```python
POWER_REPORT_RE = re.compile(r"^up:power_report:(\d+):(\d+)$", re.IGNORECASE)
```

### Wi-Fi RSSI Signal Reporting (`query`)
The server sends:
```text
up:query:wifirssi\r\n
```
The strip replies:
```text
up:query:-43\r\n
```
Value `-43` is the Wi-Fi RSSI in dBm.

**Regex:**
```python
QUERY_RE = re.compile(r"^up:query:(-?\d+)$")
```

### Relay Control (`onoff`)
To turn an outlet ON or OFF:
```text
up:onoff:<channel>:<on|off>\r\n
```
**Examples:**
* `up:onoff:1:on\r\n` (energizes outlet 1)
* `up:onoff:3:off\r\n` (de-energizes outlet 3)

The strip responds with:
```text
up:onoff:1:on\r\n
```
or an acknowledgement.

### Physical Button Push Event (`event`)
When a human presses a button on the physical unit:
```text
up:event:onoff:<channel>:<on|off>\r\n
```
* Channels `1`–`4`: Toggles individual outlet.
* Channel `0`: Toggles master power (all outlets).

**Regex:**
```python
EVENT_RE = re.compile(r"^up:event:onoff:(\d+):(on|off)$", re.IGNORECASE)
```
