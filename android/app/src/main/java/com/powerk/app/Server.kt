package com.powerk.app

import android.app.Activity
import android.app.LocaleManager
import android.content.Context
import android.content.ContextWrapper
import android.content.SharedPreferences
import android.content.res.Configuration
import android.os.Build
import android.os.LocaleList
import androidx.annotation.RequiresApi
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import java.util.Locale

/** Server & Account configuration, persisted in SharedPreferences. */
object Server {
    private var prefs: SharedPreferences? = null

    var host by mutableStateOf("13.61.25.9")
        private set
    var port by mutableIntStateOf(8080)
        private set
    var token by mutableStateOf("")
        private set
    var userName by mutableStateOf("")
        private set
    var userEmail by mutableStateOf("")
        private set
    var pinCode by mutableStateOf("")
        private set
    var biometricEnabled by mutableStateOf(false)
        private set
    var isUnlocked by mutableStateOf(true)

    fun init(context: Context) {
        val p = context.applicationContext.getSharedPreferences("na7la_powerat", Context.MODE_PRIVATE)
        prefs = p
        host = p.getString("host", "13.61.25.9").orEmpty()
        port = p.getInt("port", 8080)
        token = p.getString("token", "").orEmpty()
        userName = p.getString("user_name", "").orEmpty()
        userEmail = p.getString("user_email", "").orEmpty()
        pinCode = p.getString("pin_code", "").orEmpty()
        biometricEnabled = p.getBoolean("biometric_enabled", false)

        if (pinCode.isNotBlank() || biometricEnabled) {
            isUnlocked = false
        }
    }

    fun saveServer(newHost: String, newPort: Int, newToken: String) {
        host = newHost.trim()
        port = newPort.coerceIn(1, 65535)
        token = newToken.trim()
        prefs?.edit()
            ?.putString("host", host)
            ?.putInt("port", port)
            ?.putString("token", token)
            ?.apply()
    }

    fun saveUser(name: String, email: String, newToken: String) {
        userName = name.trim()
        userEmail = email.trim()
        token = newToken.trim()
        prefs?.edit()
            ?.putString("user_name", userName)
            ?.putString("user_email", userEmail)
            ?.putString("token", token)
            ?.apply()
    }

    fun saveSecurity(newPin: String, enableBiometric: Boolean) {
        pinCode = newPin.trim()
        biometricEnabled = enableBiometric
        prefs?.edit()
            ?.putString("pin_code", pinCode)
            ?.putBoolean("biometric_enabled", biometricEnabled)
            ?.apply()
    }

    val configured: Boolean get() = host.isNotBlank()
    val base: String get() = "http://$host:$port"
}

/** In-app language: null follows the phone language. */
object Lang {
    var code: String? = null
        private set

    private var prefs: SharedPreferences? = null

    fun init(context: Context) {
        val p = context.applicationContext.getSharedPreferences("na7la_powerat", Context.MODE_PRIVATE)
        prefs = p
        code = p.getString("lang", "").orEmpty().ifBlank { null }
    }

    /** Applies a new choice immediately: platform per-app locale on 33+, recreate below that. */
    fun set(context: Context, value: String?) {
        code = value
        prefs?.edit()?.putString("lang", value.orEmpty())?.apply()
        val activity = context.findActivity() ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            setPlatformLocales(activity, value)
        } else {
            activity.applyLocale(value)
            activity.recreate()
        }
    }

    /** Called from Activity.onCreate so the first composition already uses the stored language. */
    fun applyStored(activity: Activity) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU && code != null) {
            activity.applyLocale(code)
        }
    }

    @RequiresApi(Build.VERSION_CODES.TIRAMISU)
    private fun setPlatformLocales(activity: Activity, value: String?) {
        val manager = activity.getSystemService(LocaleManager::class.java) ?: return
        manager.applicationLocales =
            if (value == null) LocaleList.getEmptyLocaleList() else LocaleList.forLanguageTags(value)
    }

    @Suppress("DEPRECATION")
    private fun Activity.applyLocale(value: String?) {
        val locale = if (value == null) LocaleList.getDefault()[0] else Locale.forLanguageTag(value)
        Locale.setDefault(locale)
        val config = Configuration(resources.configuration).apply { setLocale(locale) }
        resources.updateConfiguration(config, resources.displayMetrics)
    }
}

internal tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}
