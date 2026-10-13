package com.powerk.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.InetSocketAddress
import java.net.Socket

sealed class ProvisionStep {
    object Idle : ProvisionStep()
    data class Connecting(val message: String) : ProvisionStep()
    data class SendingIp(val message: String) : ProvisionStep()
    data class SendingWifi(val message: String) : ProvisionStep()
    data class PowerCyclePrompt(val countdownSeconds: Int) : ProvisionStep()
    data class Success(val message: String) : ProvisionStep()
    data class Error(val error: String) : ProvisionStep()
}

object ProvisioningService {

    /**
     * Validates Wi-Fi password to prevent Gotcha 1:
     * Firmware Linux shell script corrupts /etc/wpa_supplicant.conf on '*' or '/'
     */
    fun validateCredentials(ssid: String, password: String): String? {
        if (ssid.isBlank()) return "يجب إدخال اسم شبكة الواي فاي (SSID)"
        if (password.isBlank()) return "يجب إدخال كلمة سر الواي فاي"
        if (password.contains("*") || password.contains("/") || password.contains(":")) {
            return "تحذير أمان: فيرموير المشترك لا يدعم الرموز (* أو / أو :). يرجى استخدام حروف وأرقام فقط لمنع تعطل المشترك."
        }
        return null
    }

    /**
     * Connects directly to the strip's TCP 30300 provisioning port in SoftAP mode (192.168.1.1)
     * and sends the server IP and Wi-Fi credentials.
     */
    suspend fun provision(
        stripIp: String = "192.168.1.1",
        stripPort: Int = 30300,
        serverIp: String,
        ssid: String,
        password: String,
        onProgress: (ProvisionStep) -> Unit
    ): Boolean = withContext(Dispatchers.IO) {
        val validationErr = validateCredentials(ssid, password)
        if (validationErr != null) {
            onProgress(ProvisionStep.Error(validationErr))
            return@withContext false
        }

        var socket: Socket? = null
        try {
            onProgress(ProvisionStep.Connecting("جاري الاتصال بالمشترك على $stripIp:$stripPort..."))
            socket = Socket()
            socket.soTimeout = 8000
            socket.connect(InetSocketAddress(stripIp, stripPort), 6000)

            val reader = BufferedReader(InputStreamReader(socket.getInputStream(), Charsets.US_ASCII))
            val writer = OutputStreamWriter(socket.getOutputStream(), Charsets.US_ASCII)

            // Step 1: Send Server IP
            onProgress(ProvisionStep.SendingIp("جاري إرسال عنوان السيرفر ($serverIp)..."))
            val ipCmd = "up:ip:$serverIp\r\n"
            writer.write(ipCmd)
            writer.flush()

            val ipResp = reader.readLine()
            if (ipResp == null || !ipResp.contains("ip_ok")) {
                // If strip sent something else, log but continue if not empty
                if (ipResp.isNullOrBlank()) {
                    throw Exception("المشترك لم يستجب لأمر السيرفر. تأكد من الاتصال بشبكة المشترك TONLY_TAP.")
                }
            }

            // Step 2: Send Wi-Fi credentials
            onProgress(ProvisionStep.SendingWifi("جاري إرسال بيانات الواي فاي ($ssid)..."))
            val connectCmd = "up:connect:$ssid:$password\r\n"
            writer.write(connectCmd)
            writer.flush()

            val connectResp = reader.readLine()
            if (connectResp == null || !connectResp.contains("connect_ok")) {
                if (connectResp.isNullOrBlank()) {
                    throw Exception("المشترك لم يؤكد استلام بيانات الواي فاي.")
                }
            }

            // Step 3: Success! Prompt for 20-second power cycle
            onProgress(ProvisionStep.PowerCyclePrompt(25))
            return@withContext true
        } catch (e: Exception) {
            onProgress(ProvisionStep.Error("فشلت التهيئة: ${e.message ?: "تعذر الاتصال بالمشترك"}"))
            return@withContext false
        } finally {
            try {
                socket?.close()
            } catch (_: Exception) {}
        }
    }
}
