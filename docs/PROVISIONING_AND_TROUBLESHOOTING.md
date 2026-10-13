# Provisioning & Troubleshooting Guide

This guide covers setting up physical **LG U+ / Jinheung MTTL-W01** smart power strips, pairing them with the Powerk server, and diagnosing connectivity issues.

---

## 1. Step-by-Step Provisioning Procedure

### Step 1: Ensure Prerequisites
1. You have a **2.4 GHz Wi-Fi network**.
2. **Wi-Fi Password Rule**: Ensure the password **contains NO special symbols** (`*`, `/`, `:`, or newlines). Use only alphanumeric characters (e.g. `12345678Hassan`).
3. You know the public IP of your server (e.g. `13.61.25.9`).

### Step 2: Put the Strip into Setup Mode
1. Plug the smart strip into AC power.
2. **Press and hold the master power button for ~10 seconds.**
3. Release the button when the Wi-Fi LED begins **blinking rapidly** (~5–10 Hz).
4. The strip is now broadcasting its SoftAP network:
   * **SSID**: `TONLY_TAP_XXXXXXX`
   * **Password**: `LGU_XXXXXXX` (the same 7 characters after `TONLY_TAP_`)

### Step 3: Run the Provisioning Command
Connect your laptop or mobile phone to the strip's Wi-Fi network `TONLY_TAP_XXXXXXX`.  
*(Note: Your device will say "No internet", which is expected).*

Run the provisioning command:
```bash
python powerk.py provision --ip <SERVER_PUBLIC_IP> --ssid "<WIFI_SSID>" --password "<WIFI_PASSWORD>"
```

**Expected output:**
```text
Looking for the strip's setup service at 192.168.1.1:30300 ...
  up:ip:ip_ok
  up:connect:connect_ok

Done. Reconnect this PC to your home Wi-Fi and start `python powerk.py`.
The strip will connect to <SERVER_PUBLIC_IP>:10086 shortly.
```

### Step 4: The 20-Second Power Cycle (Crucial Step!)
After the script prints `Done`:
1. **Unplug the smart strip from the 220V wall outlet completely.**
2. Wait **20 to 30 seconds** for all internal capacitors to drain.
3. Plug it back into the wall outlet.
4. The strip boots cleanly, joins your 2.4 GHz Wi-Fi, and dials `<SERVER_PUBLIC_IP>` on port `21197` (or `10086`).
5. The Wi-Fi LED turns **SOLID ON** when connected.

---

## 2. Troubleshooting & Diagnostic Matrix

| Symptom | Probable Cause | Solution |
|---|---|---|
| **LED blinks rapidly** | Device is in setup mode (SoftAP active). | Connect to `TONLY_TAP_...` and run `powerk.py provision`. |
| **LED blinks slowly (~1 Hz) indefinitely** | Wi-Fi authentication failure or band steering. | 1. Check if password has special chars (`*` or `/`). Change to simple password.<br>2. Ensure 2.4 GHz is separate from 5 GHz.<br>3. Check if WPA3 is enabled on router (switch to WPA2 Personal). |
| **Strip connects to Wi-Fi, but server shows Offline** | Firewall blocking inbound ports or wrong IP. | 1. Verify AWS Security Group has inbound TCP ports `10086` and `21197` open.<br>2. Run `Test-NetConnection -ComputerName <IP> -Port 21197`.<br>3. Power cycle strip for 20s. |
| **`strip answered '', expected 'up:ip:ip_ok'` during setup** | Laptop was not connected to `TONLY_TAP_...` or timed out. | Verify connection to `TONLY_TAP_...` before running provision. |
| **Physical buttons work, but Telegram bot / Web UI doesn't** | Device not registered in database. | Send the strip's MAC address to `@Na7laPoweratBot` in Telegram to claim it. |

---

## 3. Network Debugging Checklist for Admins

If a strip is not connecting to your VPS:

```bash
# 1. Verify both device ports are listening on the server
sudo ss -tulpn | grep -E '10086|21197'

# 2. Check live packet arrivals (from any IP)
sudo tcpdump -i any -n "port 10086 or port 21197"

# 3. Check application logs for connection events
sudo journalctl -u powerk -f | grep "powerk.hub"
```
When a strip connects successfully, you will see:
```text
[INFO] powerk.hub: Incoming connection from device at 41.39.35.239
[INFO] powerk.hub: Device registered: MTTL 2C6E5E7 (MAC: 2CE032C6E5E7, IP: 41.39.35.239, FW: 0.1.55-1.0.146)
```
