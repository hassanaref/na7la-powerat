package com.powerk.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Fingerprint
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.fragment.app.FragmentActivity
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat

@Composable
fun SecurityLockScreen(onUnlocked: () -> Unit) {
    val context = LocalContext.current
    var pinInput by remember { mutableStateOf("") }
    var errorMsg by remember { mutableStateOf<String?>(null) }

    fun checkPin() {
        if (pinInput == Server.pinCode || Server.pinCode.isBlank()) {
            Server.isUnlocked = true
            onUnlocked()
        } else {
            errorMsg = "الرقم السري غير صحيح"
            pinInput = ""
        }
    }

    LaunchedEffect(Unit) {
        if (Server.biometricEnabled && context is FragmentActivity) {
            val executor = ContextCompat.getMainExecutor(context)
            val prompt = BiometricPrompt(
                context,
                executor,
                object : BiometricPrompt.AuthenticationCallback() {
                    override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                        super.onAuthenticationSucceeded(result)
                        Server.isUnlocked = true
                        onUnlocked()
                    }
                }
            )
            val promptInfo = BiometricPrompt.PromptInfo.Builder()
                .setTitle("تأكيد الهوية")
                .setSubtitle("استخدم بصمة الإصبع أو الوجه لفتح نحلة باورات")
                .setNegativeButtonText("استخدام الرقم السري")
                .build()
            prompt.authenticate(promptInfo)
        }
    }

    Box(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(20.dp),
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)
        ) {
            Surface(
                shape = CircleShape,
                color = MaterialTheme.colorScheme.primaryContainer,
                modifier = Modifier.size(80.dp)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(
                        Icons.Filled.Lock,
                        contentDescription = null,
                        modifier = Modifier.size(42.dp),
                        tint = MaterialTheme.colorScheme.primary
                    )
                }
            }

            Text(
                "نحلة باورات 2.0",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold
            )

            Text(
                "أدخل الرقم السري للمتابعة",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            OutlinedTextField(
                value = pinInput,
                onValueChange = {
                    if (it.length <= 8) {
                        pinInput = it
                        if (it.length == Server.pinCode.length && Server.pinCode.isNotEmpty()) {
                            checkPin()
                        }
                    }
                },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                label = { Text("رمز PIN") },
                modifier = Modifier.fillMaxWidth(0.7f)
            )

            if (errorMsg != null) {
                Text(
                    errorMsg!!,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium
                )
            }

            Button(
                onClick = { checkPin() },
                modifier = Modifier.fillMaxWidth(0.7f)
            ) {
                Text("فتح القفل")
            }
        }
    }
}
