package com.powerk.app

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.DeviceThermostat
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Lightbulb
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Power
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Router
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.filled.Tv
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Slider
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableDoubleStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

@Composable
fun PowerkApp() {
    var tab by remember { mutableIntStateOf(0) }
    var snapshot by remember { mutableStateOf<Snapshot?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }
    var showSplash by remember { mutableStateOf(true) }
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val pending = remember { mutableStateMapOf<String, Boolean>() }

    suspend fun refresh() {
        if (!Server.configured) return
        loading = true
        try {
            snapshot = Api.snapshot(Server.base, Server.token)
            error = null
        } catch (e: Exception) {
            error = e.message ?: e.javaClass.simpleName
            snapshot = null
        }
        loading = false
    }

    LaunchedEffect(Unit) {
        delay(1100)
        showSplash = false
    }

    LaunchedEffect(tab, Server.host, Server.port, Server.token) {
        while (true) {
            refresh()
            delay(2500)
        }
    }

    fun command(mac: String, outlet: Int, on: Boolean) {
        val keys = if (outlet == 0) (1..4).map { "$mac:$it" } else listOf("$mac:$outlet")
        if (keys.any { pending.containsKey(it) }) return
        keys.forEach { pending[it] = on }
        scope.launch {
            try {
                Api.setOutlet(Server.base, Server.token, mac, outlet, on)
                refresh()
            } catch (e: Exception) {
                snackbar.showSnackbar(e.message ?: "command failed")
            } finally {
                keys.forEach { pending.remove(it) }
            }
        }
    }

    // Security Gate check
    if (!Server.isUnlocked && (Server.pinCode.isNotBlank() || Server.biometricEnabled)) {
        SecurityLockScreen(onUnlocked = { Server.isUnlocked = true })
        return
    }

    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Scaffold(
            containerColor = MaterialTheme.colorScheme.background,
            contentColor = MaterialTheme.colorScheme.onBackground,
            snackbarHost = { SnackbarHost(snackbar) },
            bottomBar = {
                NavigationBar {
                    NavigationBarItem(
                        selected = tab == 0,
                        onClick = { tab = 0 },
                        icon = { Icon(Icons.Filled.Home, contentDescription = null) },
                        label = { Text(stringResource(R.string.tab_plugs)) },
                    )
                    NavigationBarItem(
                        selected = tab == 1,
                        onClick = { tab = 1 },
                        icon = { Icon(Icons.Filled.Shield, contentDescription = null) },
                        label = { Text(stringResource(R.string.tab_protection)) },
                    )
                    NavigationBarItem(
                        selected = tab == 2,
                        onClick = { tab = 2 },
                        icon = { Icon(Icons.Filled.Wifi, contentDescription = null) },
                        label = { Text(stringResource(R.string.tab_setup)) },
                    )
                    NavigationBarItem(
                        selected = tab == 3,
                        onClick = { tab = 3 },
                        icon = { Icon(Icons.Filled.Settings, contentDescription = null) },
                        label = { Text(stringResource(R.string.tab_settings)) },
                    )
                }
            },
        ) { padding ->
            AnimatedContent(
                targetState = tab,
                transitionSpec = {
                    val forward = targetState > initialState
                    val shift = if (forward) 1 else -1
                    (fadeIn(tween(240)) + slideInVertically(tween(280)) { it / 10 * shift }) togetherWith
                        (fadeOut(tween(140)) + slideOutVertically(tween(200)) { -it / 14 * shift })
                },
                label = "tab",
                modifier = Modifier.fillMaxSize().padding(padding),
            ) { current ->
                when (current) {
                    0 -> PlugsScreen(
                        snapshot = snapshot,
                        error = error,
                        loading = loading,
                        pending = pending,
                        onRefresh = { scope.launch { refresh() } },
                        onOpenSettings = { tab = 3 },
                        onOpenSetup = { tab = 2 },
                        onCommand = { mac, outlet, on -> command(mac, outlet, on) },
                    )
                    1 -> ProtectionScreen(
                        snapshot = snapshot,
                        onRefresh = { scope.launch { refresh() } }
                    )
                    2 -> SetupWizardScreen(
                        onProvisioned = { mac ->
                            scope.launch {
                                try {
                                    Api.claimStrip(Server.base, Server.token, mac)
                                    refresh()
                                    tab = 0
                                } catch (_: Exception) {}
                            }
                        }
                    )
                    else -> SettingsScreen(onRefreshStrips = { scope.launch { refresh() } })
                }
            }
        }

        AnimatedVisibility(
            visible = showSplash,
            exit = fadeOut(tween(420)) + scaleOut(tween(420), targetScale = 1.06f),
        ) { Splash() }
    }
}

@Composable
private fun Splash() {
    val appear = remember { Animatable(0f) }
    LaunchedEffect(Unit) { appear.animateTo(1f, spring(dampingRatio = 0.55f, stiffness = Spring.StiffnessLow)) }
    val scheme = MaterialTheme.colorScheme

    Box(
        Modifier
            .fillMaxSize()
            .background(Brush.verticalGradient(listOf(scheme.primaryContainer, scheme.background))),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Box(
                Modifier
                    .size(140.dp)
                    .graphicsLayer {
                        val p = appear.value
                        scaleX = 0.62f + 0.38f * p
                        scaleY = 0.62f + 0.38f * p
                        alpha = p
                        rotationZ = -28f * (1f - p)
                    },
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    painter = painterResource(R.drawable.ic_launcher_foreground),
                    contentDescription = null,
                    modifier = Modifier.size(140.dp),
                    tint = Color.Unspecified,
                )
            }
            Spacer(Modifier.height(18.dp))
            Text(
                stringResource(R.string.app_name),
                style = MaterialTheme.typography.displaySmall,
                fontWeight = FontWeight.Bold,
                color = scheme.onSurface,
            )
            Text(
                stringResource(R.string.splash_tagline),
                style = MaterialTheme.typography.bodyMedium,
                color = scheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(30.dp))
            CircularProgressIndicator(Modifier.size(32.dp))
        }
    }
}

@Composable
private fun PlugsScreen(
    snapshot: Snapshot?,
    error: String?,
    loading: Boolean,
    pending: Map<String, Boolean>,
    onRefresh: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenSetup: () -> Unit,
    onCommand: (String, Int, Boolean) -> Unit,
) {
    val strips = snapshot?.strips.orEmpty()
    var editingOutlet by remember { mutableStateOf<Pair<Strip, Outlet>?>(null) }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = 20.dp, bottom = 36.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            Header(
                stripCount = strips.size,
                onlineCount = strips.count { it.online },
                configured = Server.configured,
                loading = loading,
                onRefresh = onRefresh,
            )
        }

        item {
            AnimatedVisibility(
                visible = error != null,
                enter = fadeIn() + slideInVertically { -it / 3 },
                exit = fadeOut(),
            ) {
                MessageCard(error ?: "", isError = true, icon = Icons.Filled.Warning)
            }
        }

        if (!Server.configured) {
            item {
                EmptyState(
                    title = stringResource(R.string.no_server_title),
                    body = stringResource(R.string.no_server_body),
                    action = stringResource(R.string.open_settings),
                    onAction = onOpenSettings,
                )
            }
        } else {
            if (strips.isNotEmpty()) {
                item {
                    ScenesBar(
                        strips = strips,
                        onCommand = onCommand
                    )
                }
            }

            items(strips, key = { it.mac }) { strip ->
                StripCard(
                    strip = strip,
                    showMac = strips.size > 1,
                    pending = pending,
                    onCommand = onCommand,
                    onEditOutlet = { outlet -> editingOutlet = Pair(strip, outlet) }
                )
            }

            if (snapshot != null && strips.isEmpty()) {
                item {
                    EmptyState(
                        title = stringResource(R.string.no_strip_title),
                        body = stringResource(R.string.no_strip_body),
                        action = stringResource(R.string.tab_setup),
                        onAction = onOpenSetup,
                    )
                }
            }
        }
    }

    editingOutlet?.let { (strip, outlet) ->
        OutletEditDialog(
            strip = strip,
            outlet = outlet,
            onDismiss = { editingOutlet = null },
            onSaved = {
                editingOutlet = null
                onRefresh()
            }
        )
    }
}

@Composable
private fun Header(
    stripCount: Int,
    onlineCount: Int,
    configured: Boolean,
    loading: Boolean,
    onRefresh: () -> Unit,
) {
    val spin = rememberInfiniteTransition(label = "refresh")
    val angle by spin.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(900, easing = LinearEasing)),
        label = "angle",
    )
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(
                stringResource(R.string.app_name),
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
            )
            val subtitle = when {
                !configured -> stringResource(R.string.header_no_server)
                onlineCount > 0 -> stringResource(R.string.header_online, onlineCount, Server.host)
                stripCount > 0 -> stringResource(R.string.header_known_offline, stripCount)
                else -> stringResource(R.string.header_waiting, Server.host)
            }
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        IconButton(onClick = onRefresh, enabled = configured && !loading) {
            Icon(
                Icons.Filled.Refresh,
                contentDescription = stringResource(R.string.refresh),
                modifier = Modifier.rotate(if (loading) angle else 0f),
            )
        }
    }
}

@Composable
private fun ScenesBar(
    strips: List<Strip>,
    onCommand: (String, Int, Boolean) -> Unit
) {
    ElevatedCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(stringResource(R.string.scenes_title), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                item {
                    Button(
                        onClick = {
                            strips.forEach { s ->
                                onCommand(s.mac, 1, true)
                                onCommand(s.mac, 2, true)
                                onCommand(s.mac, 3, true)
                            }
                        },
                        shape = RoundedCornerShape(12.dp)
                    ) { Text(stringResource(R.string.scene_work)) }
                }
                item {
                    FilledTonalButton(
                        onClick = {
                            strips.forEach { s ->
                                onCommand(s.mac, 1, true) // keep router
                                onCommand(s.mac, 2, false)
                                onCommand(s.mac, 3, false)
                                onCommand(s.mac, 4, false)
                            }
                        },
                        shape = RoundedCornerShape(12.dp)
                    ) { Text(stringResource(R.string.scene_sleep)) }
                }
                item {
                    FilledTonalButton(
                        onClick = {
                            strips.forEach { s ->
                                onCommand(s.mac, 3, true) // TV
                                onCommand(s.mac, 4, false)
                            }
                        },
                        shape = RoundedCornerShape(12.dp)
                    ) { Text(stringResource(R.string.scene_cinema)) }
                }
                item {
                    OutlinedButton(
                        onClick = { strips.forEach { s -> onCommand(s.mac, 0, true) } },
                        shape = RoundedCornerShape(12.dp)
                    ) { Text(stringResource(R.string.scene_all_on)) }
                }
                item {
                    OutlinedButton(
                        onClick = { strips.forEach { s -> onCommand(s.mac, 0, false) } },
                        shape = RoundedCornerShape(12.dp)
                    ) { Text(stringResource(R.string.scene_all_off)) }
                }
            }
        }
    }
}

@Composable
private fun StripCard(
    strip: Strip,
    showMac: Boolean,
    pending: Map<String, Boolean>,
    onCommand: (String, Int, Boolean) -> Unit,
    onEditOutlet: (Outlet) -> Unit,
) {
    val stateOf: (Int) -> Boolean = { n -> pending["${strip.mac}:$n"] ?: strip.outletOn(n) }
    val anyOn = (1..4).any(stateOf)

    ElevatedCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                StatusDot(online = strip.online)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    val title = strip.name + if (showMac) " · ${strip.mac.takeLast(6)}" else ""
                    Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                    Text(
                        stringResource(R.string.strip_fw, strip.fw),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Button(
                    onClick = { onCommand(strip.mac, 0, !anyOn) },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (anyOn) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary
                    )
                ) {
                    Text(if (anyOn) stringResource(R.string.turn_all_off) else stringResource(R.string.turn_all_on))
                }
            }

            // Power Metrics Bar
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                PowerRing(watts = strip.powerW, enabled = strip.online)
                Column(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.weight(1f)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        MetricPill("${strip.energyKwh} kWh")
                        strip.voltage?.let { MetricPill("${it.roundToInt()} V") }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        strip.currentA?.let { MetricPill("$it A") }
                        strip.rssi?.let { MetricPill("$it dBm") }
                    }
                }
            }

            // 4 Outlets Grid (2x2)
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                for (row in 0 until 2) {
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        for (col in 0 until 2) {
                            val outlet = strip.outlets.getOrNull(row * 2 + col)
                            if (outlet != null) {
                                Box(Modifier.weight(1f)) {
                                    OutletTile(
                                        outlet = outlet,
                                        on = stateOf(outlet.n),
                                        onToggle = { onCommand(strip.mac, outlet.n, !stateOf(outlet.n)) },
                                        onEdit = { onEditOutlet(outlet) }
                                    )
                                }
                            } else {
                                Spacer(Modifier.weight(1f))
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun OutletTile(
    outlet: Outlet,
    on: Boolean,
    onToggle: () -> Unit,
    onEdit: () -> Unit
) {
    val bg = if (on) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant
    val contentColor = if (on) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant

    Card(
        colors = CardDefaults.cardColors(containerColor = bg, contentColor = contentColor),
        shape = RoundedCornerShape(16.dp),
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onToggle() }
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    getOutletIcon(outlet.icon),
                    contentDescription = null,
                    modifier = Modifier.size(26.dp),
                    tint = if (on) MaterialTheme.colorScheme.primary else contentColor
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    outlet.name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.weight(1f),
                    maxLines = 1
                )
                IconButton(onClick = onEdit, modifier = Modifier.size(24.dp)) {
                    Icon(Icons.Filled.Edit, contentDescription = "Edit", modifier = Modifier.size(16.dp))
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    if (on) stringResource(R.string.state_on) else stringResource(R.string.state_off),
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelLarge
                )
                Text(
                    if (on) "${outlet.powerW.roundToInt()} W" else "${outlet.tempC}°C",
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }
    }
}

fun getOutletIcon(name: String): ImageVector = when (name.lowercase()) {
    "router" -> Icons.Filled.Router
    "pc", "computer" -> Icons.Filled.Computer
    "tv" -> Icons.Filled.Tv
    "lamp", "light" -> Icons.Filled.Lightbulb
    else -> Icons.Filled.Power
}

@Composable
private fun OutletEditDialog(
    strip: Strip,
    outlet: Outlet,
    onDismiss: () -> Unit,
    onSaved: () -> Unit
) {
    val scope = rememberCoroutineScope()
    var name by remember { mutableStateOf(outlet.name) }
    var selectedIcon by remember { mutableStateOf(outlet.icon) }
    var autoOffMins by remember { mutableStateOf(outlet.autoOffMinutes.toString()) }
    var standbyW by remember { mutableStateOf(outlet.standbyCutoffW.toString()) }
    var busy by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("تخصيص المخرج ${outlet.n}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("اسم المخرج (مثل: الراوتر، الكمبيوتر)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                Text("الأيقونة:", style = MaterialTheme.typography.labelMedium)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("outlet", "router", "pc", "tv", "lamp").forEach { ic ->
                        IconButton(
                            onClick = { selectedIcon = ic },
                            modifier = Modifier
                                .background(
                                    if (selectedIcon == ic) MaterialTheme.colorScheme.primaryContainer else Color.Transparent,
                                    CircleShape
                                )
                        ) {
                            Icon(getOutletIcon(ic), contentDescription = ic)
                        }
                    }
                }

                OutlinedTextField(
                    value = autoOffMins,
                    onValueChange = { autoOffMins = it.filter(Char::isDigit) },
                    label = { Text("إطفاء تلقائي بعد (دقائق - 0 للتعطيل)") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = standbyW,
                    onValueChange = { standbyW = it },
                    label = { Text("فصل عند الخمول أقل من (وات - 0 للتعطيل)") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        },
        confirmButton = {
            Button(
                enabled = !busy,
                onClick = {
                    busy = true
                    scope.launch {
                        try {
                            Api.updateOutletSmart(
                                base = Server.base,
                                token = Server.token,
                                mac = strip.mac,
                                channel = outlet.n,
                                name = name,
                                icon = selectedIcon,
                                autoOffMinutes = autoOffMins.toIntOrNull() ?: 0,
                                standbyCutoffW = standbyW.toDoubleOrNull() ?: 0.0
                            )
                            onSaved()
                        } catch (_: Exception) {
                            busy = false
                        }
                    }
                }
            ) { Text("حفظ") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("إلغاء") }
        }
    )
}

@Composable
private fun ProtectionScreen(
    snapshot: Snapshot?,
    onRefresh: () -> Unit
) {
    val strip = snapshot?.strips?.firstOrNull()
    val scope = rememberCoroutineScope()
    var minV by remember { mutableDoubleStateOf(strip?.minVoltage ?: 190.0) }
    var maxV by remember { mutableDoubleStateOf(strip?.maxVoltage ?: 245.0) }
    var maxW by remember { mutableDoubleStateOf(strip?.maxPowerW ?: 3200.0) }
    var childLock by remember { mutableStateOf(strip?.childLockEnabled ?: false) }
    var awayMode by remember { mutableStateOf(strip?.awayModeEnabled ?: false) }
    var routerCh by remember { mutableIntStateOf(strip?.surgeRouterChannel ?: 1) }
    var saving by remember { mutableStateOf(false) }
    var savedMessage by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(strip) {
        if (strip != null) {
            minV = strip.minVoltage
            maxV = strip.maxVoltage
            maxW = strip.maxPowerW
            childLock = strip.childLockEnabled
            awayMode = strip.awayModeEnabled
            routerCh = strip.surgeRouterChannel
        }
    }

    fun save() {
        if (strip == null) return
        saving = true
        scope.launch {
            try {
                Api.updateProtection(
                    base = Server.base,
                    token = Server.token,
                    settings = ProtectionSettings(
                        mac = strip.mac,
                        minVoltage = minV,
                        maxVoltage = maxV,
                        maxPowerW = maxW,
                        childLockEnabled = childLock,
                        awayModeEnabled = awayMode,
                        surgeRouterChannel = routerCh
                    )
                )
                savedMessage = "تم حفظ إعدادات الحماية بنجاح!"
                onRefresh()
            } catch (e: Exception) {
                savedMessage = "فشل الحفظ: ${e.message}"
            }
            saving = false
        }
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            stringResource(R.string.protection_title),
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )
        Text(
            stringResource(R.string.protection_subtitle),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        if (strip == null) {
            MessageCard("لا يوجد مشترك متصل لتعديل إعدادات الحماية.", isError = true, icon = Icons.Filled.Warning)
            return
        }

        // Live Voltage Guard Card
        ElevatedCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.Bolt, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.voltage_guard), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                }
                Text(stringResource(R.string.voltage_guard_desc), style = MaterialTheme.typography.bodySmall)

                Text("الحد الأدنى للجهد: ${minV.roundToInt()} فولت")
                Slider(
                    value = minV.toFloat(),
                    onValueChange = { minV = it.toDouble().roundToInt().toDouble() },
                    valueRange = 160f..210f,
                    steps = 50
                )

                Text("الحد الأقصى للجهد: ${maxV.roundToInt()} فولت")
                Slider(
                    value = maxV.toFloat(),
                    onValueChange = { maxV = it.toDouble().roundToInt().toDouble() },
                    valueRange = 230f..260f,
                    steps = 30
                )
            }
        }

        // Overload Limit Card
        ElevatedCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.Security, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.overload_limit), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                }
                Text(stringResource(R.string.overload_desc), style = MaterialTheme.typography.bodySmall)
                Text("أقصى حمل مسموح: ${maxW.roundToInt()} وات")
                Slider(
                    value = maxW.toFloat(),
                    onValueChange = { maxW = it.toDouble().roundToInt().toDouble() },
                    valueRange = 1000f..3500f,
                    steps = 25
                )
            }
        }

        // Child Lock & Cold Boot Router Card
        ElevatedCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(stringResource(R.string.child_lock), fontWeight = FontWeight.Bold)
                        Text(stringResource(R.string.child_lock_desc), style = MaterialTheme.typography.bodySmall)
                    }
                    Switch(checked = childLock, onCheckedChange = { childLock = it })
                }

                HorizontalDivider()

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(stringResource(R.string.cold_boot_router), fontWeight = FontWeight.Bold)
                        Text(stringResource(R.string.cold_boot_desc), style = MaterialTheme.typography.bodySmall)
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    (1..4).forEach { ch ->
                        FilledTonalButton(
                            onClick = { routerCh = ch },
                            colors = ButtonDefaults.filledTonalButtonColors(
                                containerColor = if (routerCh == ch) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant
                            )
                        ) {
                            Text("المخرج $ch")
                        }
                    }
                }

                HorizontalDivider()

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(stringResource(R.string.away_mode), fontWeight = FontWeight.Bold)
                        Text(stringResource(R.string.away_mode_desc), style = MaterialTheme.typography.bodySmall)
                    }
                    Switch(checked = awayMode, onCheckedChange = { awayMode = it })
                }
            }
        }

        Button(
            onClick = { save() },
            enabled = !saving,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("حفظ وتطبيق إعدادات الحماية")
        }

        savedMessage?.let { msg ->
            Text(msg, color = MaterialTheme.colorScheme.primary, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
        }
    }
}

@Composable
private fun SetupWizardScreen(
    onProvisioned: (String) -> Unit
) {
    val scope = rememberCoroutineScope()
    var ssid by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var serverIp by remember { mutableStateOf(Server.host) }
    var warningSpecial by remember { mutableStateOf<String?>(null) }
    var currentStep by remember { mutableStateOf<ProvisionStep>(ProvisionStep.Idle) }
    var countdown by remember { mutableIntStateOf(25) }

    LaunchedEffect(password) {
        warningSpecial = if (password.contains("*") || password.contains("/") || password.contains(":")) {
            "⚠️ تحذير: فيرموير المشترك يتعطل إذا كانت كلمة السر تحتوي على * أو /. استخدم حروفاً وأرقاماً فقط!"
        } else null
    }

    fun startProvisioning() {
        scope.launch {
            ProvisioningService.provision(
                serverIp = serverIp,
                ssid = ssid,
                password = password,
                onProgress = { step ->
                    currentStep = step
                    if (step is ProvisionStep.PowerCyclePrompt) {
                        countdown = step.countdownSeconds
                    }
                }
            )
        }
    }

    LaunchedEffect(currentStep) {
        if (currentStep is ProvisionStep.PowerCyclePrompt) {
            while (countdown > 0) {
                delay(1000)
                countdown--
            }
            currentStep = ProvisionStep.Success("اكتملت التهيئة بنجاح! المشترك يتصل الآن بالسيرفر.")
        }
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            stringResource(R.string.prov_title),
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )

        // Step 1
        ElevatedCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(stringResource(R.string.prov_step1_title), fontWeight = FontWeight.Bold)
                Text(stringResource(R.string.prov_step1_body), style = MaterialTheme.typography.bodySmall)
            }
        }

        // Step 2
        ElevatedCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(stringResource(R.string.prov_step2_title), fontWeight = FontWeight.Bold)

                CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr) {
                    OutlinedTextField(
                        value = ssid,
                        onValueChange = { ssid = it },
                        label = { Text(stringResource(R.string.prov_ssid)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )

                    OutlinedTextField(
                        value = password,
                        onValueChange = { password = it },
                        label = { Text(stringResource(R.string.prov_password)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )

                    OutlinedTextField(
                        value = serverIp,
                        onValueChange = { serverIp = it },
                        label = { Text(stringResource(R.string.prov_server_ip)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                }

                if (warningSpecial != null) {
                    Text(
                        warningSpecial!!,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.Bold
                    )
                }

                Button(
                    onClick = { startProvisioning() },
                    enabled = ssid.isNotBlank() && password.isNotBlank() && warningSpecial == null,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(stringResource(R.string.prov_btn_send))
                }
            }
        }

        // Status Card
        when (val s = currentStep) {
            is ProvisionStep.Connecting -> MessageCard(s.message, isError = false, icon = Icons.Filled.Wifi)
            is ProvisionStep.SendingIp -> MessageCard(s.message, isError = false, icon = Icons.Filled.Wifi)
            is ProvisionStep.SendingWifi -> MessageCard(s.message, isError = false, icon = Icons.Filled.Wifi)
            is ProvisionStep.PowerCyclePrompt -> {
                ElevatedCard(Modifier.fillMaxWidth(), colors = CardDefaults.elevatedCardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            stringResource(R.string.prov_cycle_reminder),
                            color = MaterialTheme.colorScheme.onErrorContainer,
                            fontWeight = FontWeight.Bold,
                            textAlign = TextAlign.Center
                        )
                        Text(
                            "$countdown ثانية",
                            fontSize = 32.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onErrorContainer
                        )
                    }
                }
            }
            is ProvisionStep.Success -> {
                MessageCard(s.message, isError = false, icon = Icons.Filled.Check)
            }
            is ProvisionStep.Error -> {
                MessageCard(s.error, isError = true, icon = Icons.Filled.Warning)
            }
            else -> {}
        }
    }
}

@Composable
private fun SettingsScreen(
    onRefreshStrips: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var host by remember { mutableStateOf(Server.host) }
    var port by remember { mutableStateOf(Server.port.toString()) }
    var token by remember { mutableStateOf(Server.token) }
    var lang by remember { mutableStateOf(Lang.code) }
    var status by remember { mutableStateOf<String?>(null) }
    var statusOk by remember { mutableStateOf(false) }
    var claimMac by remember { mutableStateOf("") }
    var pinSetting by remember { mutableStateOf(Server.pinCode) }
    var biometricSetting by remember { mutableStateOf(Server.biometricEnabled) }

    fun commitServer() = Server.saveServer(host, port.toIntOrNull() ?: 8080, token)
    fun commitSecurity() = Server.saveSecurity(pinSetting, biometricSetting)

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(
            stringResource(R.string.settings_title),
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
        )

        // Account & Multi-Tenancy Card
        ElevatedCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(stringResource(R.string.account_title), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text("معرف الحساب / Token الخاص بك: ${Server.token.take(16)}...", style = MaterialTheme.typography.bodySmall)

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = {
                            scope.launch {
                                try {
                                    val res = Api.signup(Server.base, "مستخدم جديد", null, null)
                                    val newToken = res.getString("user_token")
                                    token = newToken
                                    Server.saveUser("User", "", newToken)
                                    status = "تم إنشاء الحساب بنجاح!"
                                    statusOk = true
                                    onRefreshStrips()
                                } catch (e: Exception) {
                                    status = "فشل إنشاء الحساب: ${e.message}"
                                    statusOk = false
                                }
                            }
                        },
                        modifier = Modifier.weight(1f)
                    ) { Text(stringResource(R.string.btn_signup)) }
                }

                HorizontalDivider()

                Text(stringResource(R.string.claim_strip), fontWeight = FontWeight.Bold)
                CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr) {
                    OutlinedTextField(
                        value = claimMac,
                        onValueChange = { claimMac = it.uppercase() },
                        label = { Text(stringResource(R.string.field_mac)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
                Button(
                    onClick = {
                        scope.launch {
                            try {
                                val res = Api.claimStrip(Server.base, Server.token, claimMac)
                                status = res.optString("message", "تم ربط المشترك بحسابك!")
                                statusOk = true
                                onRefreshStrips()
                            } catch (e: Exception) {
                                status = "تعذر ربط المشترك: ${e.message}"
                                statusOk = false
                            }
                        }
                    },
                    enabled = claimMac.isNotBlank(),
                    modifier = Modifier.fillMaxWidth()
                ) { Text("ربط هذا المشترك بحسابي") }
            }
        }

        // Security Lock Card
        ElevatedCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(stringResource(R.string.security_title), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                OutlinedTextField(
                    value = pinSetting,
                    onValueChange = { pinSetting = it.filter(Char::isDigit).take(8) },
                    label = { Text(stringResource(R.string.set_pin)) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(stringResource(R.string.biometric_enable))
                    Switch(checked = biometricSetting, onCheckedChange = { biometricSetting = it })
                }
                Button(onClick = { commitSecurity(); status = "تم تحديث إعدادات الأمان!"; statusOk = true }) {
                    Text(stringResource(R.string.save))
                }
            }
        }

        // Server Connection Card
        ElevatedCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text(stringResource(R.string.server_title), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(stringResource(R.string.server_body), style = MaterialTheme.typography.bodySmall)

                CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr) {
                    OutlinedTextField(
                        value = host,
                        onValueChange = { host = it },
                        label = { Text(stringResource(R.string.field_host)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        OutlinedTextField(
                            value = port,
                            onValueChange = { port = it.filter(Char::isDigit).take(5) },
                            label = { Text(stringResource(R.string.field_port)) },
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            modifier = Modifier.weight(1f),
                        )
                        OutlinedTextField(
                            value = token,
                            onValueChange = { token = it },
                            label = { Text(stringResource(R.string.field_token)) },
                            singleLine = true,
                            modifier = Modifier.weight(1.4f),
                        )
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Button(
                        onClick = {
                            commitServer()
                            status = context.getString(R.string.saved)
                            statusOk = true
                        },
                        modifier = Modifier.weight(1f),
                    ) { Text(stringResource(R.string.save)) }
                    FilledTonalButton(
                        onClick = {
                            commitServer()
                            scope.launch {
                                try {
                                    val snap = Api.snapshot(Server.base, Server.token)
                                    status = context.getString(R.string.connected_summary, snap.strips.size, snap.strips.count { it.online })
                                    statusOk = true
                                } catch (e: Exception) {
                                    status = e.message ?: "connection failed"
                                    statusOk = false
                                }
                            }
                        },
                        modifier = Modifier.weight(1f),
                    ) { Text(stringResource(R.string.test)) }
                }
            }
        }

        // Language Switcher Card
        ElevatedCard(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text(stringResource(R.string.language_title), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                val options = listOf(
                    null to stringResource(R.string.lang_system),
                    "en" to stringResource(R.string.lang_english),
                    "ar" to stringResource(R.string.lang_arabic),
                )
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    options.forEachIndexed { index, (value, label) ->
                        SegmentedButton(
                            selected = lang == value,
                            onClick = {
                                if (lang != value) {
                                    lang = value
                                    Lang.set(context, value)
                                }
                            },
                            shape = SegmentedButtonDefaults.itemShape(index = index, count = options.size),
                        ) { Text(label) }
                    }
                }
            }
        }

        status?.let {
            MessageCard(it, isError = !statusOk, icon = if (statusOk) Icons.Filled.Check else Icons.Filled.Warning)
        }
    }
}

@Composable
private fun StatusDot(online: Boolean) {
    val color = if (online) Color(0xFF10B981) else Color(0xFFEF4444)
    Box(
        Modifier
            .size(10.dp)
            .background(color, CircleShape)
    )
}

@Composable
private fun MetricPill(text: String) {
    Surface(
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
    ) {
        Text(
            text,
            Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun PowerRing(watts: Double, enabled: Boolean) {
    val scheme = MaterialTheme.colorScheme
    val trackColor = scheme.surfaceVariant
    val activeColor = if (enabled) scheme.primary else scheme.outlineVariant

    Box(Modifier.size(100.dp), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val stroke = 8.dp.toPx()
            val radius = (size.minDimension - stroke) / 2
            drawCircle(
                color = trackColor,
                radius = radius,
                style = Stroke(stroke)
            )
            val sweep = ((watts / 3500.0).coerceIn(0.0, 1.0) * 360f).toFloat()
            drawArc(
                color = activeColor,
                startAngle = -90f,
                sweepAngle = if (enabled) sweep else 0f,
                useCenter = false,
                style = Stroke(stroke, cap = StrokeCap.Round)
            )
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                "${watts.roundToInt()}",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            Text("W", style = MaterialTheme.typography.labelSmall, color = scheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun MessageCard(text: String, isError: Boolean, icon: ImageVector) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = if (isError) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.primaryContainer,
        contentColor = if (isError) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onPrimaryContainer,
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, contentDescription = null, modifier = Modifier.size(24.dp))
            Spacer(Modifier.width(12.dp))
            Text(text, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun EmptyState(
    title: String,
    body: String,
    action: String? = null,
    onAction: (() -> Unit)? = null
) {
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Column(
            Modifier.padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(body, style = MaterialTheme.typography.bodySmall, textAlign = TextAlign.Center)
            if (action != null && onAction != null) {
                Button(onClick = onAction) { Text(action) }
            }
        }
    }
}
