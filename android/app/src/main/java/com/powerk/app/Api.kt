package com.powerk.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class Outlet(
    val n: Int,
    val name: String = "المخرج $n",
    val icon: String = "outlet",
    val on: Boolean = false,
    val powerW: Double = 0.0,
    val energyKwh: Double = 0.0,
    val tempC: Int = 0,
    val autoOffMinutes: Int = 0,
    val standbyCutoffW: Double = 0.0,
    val isSurgePriority: Boolean = false,
)

data class Strip(
    val mac: String,
    val name: String,
    val model: String,
    val fw: String,
    val online: Boolean,
    val on: Boolean,
    val powerW: Double,
    val energyKwh: Double,
    val voltage: Double?,
    val currentA: Double?,
    val rssi: Int?,
    val minVoltage: Double = 190.0,
    val maxVoltage: Double = 245.0,
    val maxPowerW: Double = 3200.0,
    val childLockEnabled: Boolean = false,
    val awayModeEnabled: Boolean = false,
    val surgeRouterChannel: Int = 1,
    val outlets: List<Outlet>,
)

data class Snapshot(val serverIp: String, val strips: List<Strip>)

data class ProtectionSettings(
    val mac: String,
    val minVoltage: Double,
    val maxVoltage: Double,
    val maxPowerW: Double,
    val childLockEnabled: Boolean,
    val awayModeEnabled: Boolean,
    val surgeRouterChannel: Int,
)

data class EnergySummary(
    val totalKwh: Double,
    val todayKwh: Double,
    val todayCostEgp: Double,
    val totalCostEgp: Double,
    val ratePerKwh: Double,
)

/** Outlet by its number (1..4) - never by list position. */
fun Strip.outletOn(n: Int): Boolean = outlets.firstOrNull { it.n == n }?.on ?: false
fun Strip.outlet(n: Int): Outlet? = outlets.firstOrNull { it.n == n }

class ServerException(message: String) : Exception(message)

/** Talks to the Na7la Powerat backend API. */
object Api {

    suspend fun snapshot(base: String, token: String): Snapshot = withContext(Dispatchers.IO) {
        val root = JSONObject(request("$base/api/state", null, token))
        val array = root.optJSONArray("devices")
        val strips = (0 until (array?.length() ?: 0)).map { parseStrip(array!!.getJSONObject(it)) }
        Snapshot(root.optString("local_ip"), strips)
    }

    suspend fun setOutlet(base: String, token: String, mac: String, outlet: Int, on: Boolean) = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("mac", mac)
            .put("outlet", outlet)
            .put("on", on)
            .toString()
        val response = JSONObject(request("$base/api/onoff", body, token))
        if (!response.optBoolean("ok")) {
            throw ServerException(response.optString("error").ifBlank { "command failed" })
        }
    }

    suspend fun signup(base: String, name: String, email: String?, pin: String?): JSONObject = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("name", name)
            .put("email", email)
            .put("pin_code", pin)
            .toString()
        JSONObject(request("$base/api/v1/auth/signup", body, ""))
    }

    suspend fun login(base: String, token: String?, email: String?): JSONObject = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("user_token", token)
            .put("email", email)
            .toString()
        JSONObject(request("$base/api/v1/auth/login", body, ""))
    }

    suspend fun claimStrip(base: String, token: String, mac: String): JSONObject = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("mac", mac)
            .toString()
        JSONObject(request("$base/api/v1/auth/claim", body, token))
    }

    suspend fun getProtection(base: String, token: String, mac: String): ProtectionSettings = withContext(Dispatchers.IO) {
        val res = JSONObject(request("$base/api/v1/devices/$mac/protection", null, token))
        ProtectionSettings(
            mac = res.optString("mac"),
            minVoltage = res.optDouble("min_voltage", 190.0),
            maxVoltage = res.optDouble("max_voltage", 245.0),
            maxPowerW = res.optDouble("max_power_w", 3200.0),
            childLockEnabled = res.optBoolean("child_lock_enabled", false),
            awayModeEnabled = res.optBoolean("away_mode_enabled", false),
            surgeRouterChannel = res.optInt("surge_router_channel", 1),
        )
    }

    suspend fun updateProtection(base: String, token: String, settings: ProtectionSettings): JSONObject = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("min_voltage", settings.minVoltage)
            .put("max_voltage", settings.maxVoltage)
            .put("max_power_w", settings.maxPowerW)
            .put("child_lock_enabled", settings.childLockEnabled)
            .put("away_mode_enabled", settings.awayModeEnabled)
            .put("surge_router_channel", settings.surgeRouterChannel)
            .toString()
        JSONObject(request("$base/api/v1/devices/${settings.mac}/protection", body, token, method = "PUT"))
    }

    suspend fun updateOutletSmart(
        base: String,
        token: String,
        mac: String,
        channel: Int,
        name: String?,
        icon: String?,
        autoOffMinutes: Int?,
        standbyCutoffW: Double?
    ): JSONObject = withContext(Dispatchers.IO) {
        val body = JSONObject().apply {
            name?.let { put("name", it) }
            icon?.let { put("icon", it) }
            autoOffMinutes?.let { put("auto_off_minutes", it) }
            standbyCutoffW?.let { put("standby_cutoff_w", it) }
        }.toString()
        JSONObject(request("$base/api/v1/outlets/$mac/$channel/smart", body, token, method = "PATCH"))
    }

    suspend fun getEnergySummary(base: String, token: String, mac: String): EnergySummary = withContext(Dispatchers.IO) {
        val res = JSONObject(request("$base/api/v1/stats/$mac", null, token))
        EnergySummary(
            totalKwh = res.optDouble("total_kwh", 0.0),
            todayKwh = res.optDouble("today_kwh", 0.0),
            todayCostEgp = res.optDouble("today_cost_egp", 0.0),
            totalCostEgp = res.optDouble("total_cost_egp", 0.0),
            ratePerKwh = res.optDouble("rate_per_kwh", 2.14),
        )
    }

    suspend fun createCountdown(base: String, token: String, mac: String, channel: Int, action: String, delaySeconds: Int): JSONObject = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("device_mac", mac)
            .put("outlet_channel", channel)
            .put("action", action)
            .put("delay_seconds", delaySeconds)
            .toString()
        JSONObject(request("$base/api/v1/schedules/countdown", body, token))
    }

    internal fun request(url: String, body: String?, token: String, method: String? = null): String {
        val connection = (URL(url).openConnection() as HttpURLConnection)
        try {
            connection.connectTimeout = 4000
            connection.readTimeout = 6000
            connection.requestMethod = method ?: (if (body == null) "GET" else "POST")
            if (token.isNotBlank()) {
                connection.setRequestProperty("X-User-Token", token)
                connection.setRequestProperty("X-Token", token)
                connection.setRequestProperty("Authorization", "Bearer $token")
            }
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (code !in 200..299) throw ServerException(errorOf(text, code))
            return text
        } catch (e: ServerException) {
            throw e
        } catch (e: Exception) {
            throw ServerException(e.message ?: "connection failed")
        } finally {
            connection.disconnect()
        }
    }

    private fun errorOf(body: String, code: Int): String =
        try {
            val json = JSONObject(body)
            json.optString("detail").ifBlank { json.optString("error").ifBlank { "HTTP $code" } }
        } catch (e: Exception) {
            "HTTP $code"
        }

    private fun parseStrip(o: JSONObject): Strip {
        val array = o.optJSONArray("outlets")
        val outlets = (0 until (array?.length() ?: 0)).map { i ->
            val x = array!!.getJSONObject(i)
            Outlet(
                n = x.optInt("n", i + 1),
                name = x.optString("name", "مخرج ${i + 1}"),
                icon = x.optString("icon", "outlet"),
                on = x.optBoolean("on"),
                powerW = x.optDouble("power_w", 0.0),
                energyKwh = x.optDouble("energy_kwh", 0.0),
                tempC = x.optInt("temp_c"),
                autoOffMinutes = x.optInt("auto_off_minutes", 0),
                standbyCutoffW = x.optDouble("standby_cutoff_w", 0.0),
                isSurgePriority = x.optBoolean("is_surge_priority", false),
            )
        }
        return Strip(
            mac = o.optString("mac"),
            name = o.optString("name", "مشترك نحلة باورات"),
            model = o.optString("model", "MTTL-W01"),
            fw = o.optString("fw", "0.1.55"),
            online = o.optBoolean("online"),
            on = o.optBoolean("on"),
            powerW = o.optDouble("power_w", 0.0),
            energyKwh = o.optDouble("energy_kwh", 0.0),
            voltage = o.optDoubleOrNull("voltage"),
            currentA = o.optDoubleOrNull("current_a"),
            rssi = if (o.isNull("rssi")) null else o.optInt("rssi"),
            minVoltage = o.optDouble("min_voltage", 190.0),
            maxVoltage = o.optDouble("max_voltage", 245.0),
            maxPowerW = o.optDouble("max_power_w", 3200.0),
            childLockEnabled = o.optBoolean("child_lock_enabled", false),
            awayModeEnabled = o.optBoolean("away_mode_enabled", false),
            surgeRouterChannel = o.optInt("surge_router_channel", 1),
            outlets = outlets,
        )
    }

    private fun JSONObject.optDoubleOrNull(key: String): Double? =
        if (isNull(key)) null else optDouble(key)
}
