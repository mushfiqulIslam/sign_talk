package com.signtalk.app

import android.Manifest.permission.BLUETOOTH
import android.Manifest.permission.BLUETOOTH_CONNECT
import android.Manifest.permission.RECORD_AUDIO
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts.RequestMultiplePermissions
import androidx.activity.viewModels
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleOut
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.graphics.graphicsLayer
import kotlinx.coroutines.delay
import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.meta.wearable.dat.core.Wearables
import com.meta.wearable.dat.core.types.RegistrationState

/** Meta's own small test clip (266 x 150), already within the lens video limits. */
private const val TEST_VIDEO_URL =
    "https://raw.githubusercontent.com/facebook/meta-wearables-dat-android/refs/heads/assets/video_266x150_faststart.mp4"

class MainActivity : ComponentActivity() {

  private val vm: CaptionViewModel by viewModels()

  private val permissions =
      registerForActivityResult(RequestMultiplePermissions()) { results ->
        if (results.values.all { it }) {
          vm.startAll()
        } else {
          Toast.makeText(this, "Bluetooth and microphone permissions are needed", Toast.LENGTH_LONG)
              .show()
        }
      }

  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    setContent {
      MaterialTheme(colorScheme = SignTalkColors) {
        Surface(Modifier.fillMaxSize(), color = Bg) {
          var intro by remember { mutableStateOf(true) }
          Box(Modifier.fillMaxSize()) {
            CaptionScreen(
                vm,
                onScanQr = { scanGloveQr() },
                onRegister = { Wearables.startRegistration(this@MainActivity) },
                onUnregister = { Wearables.startUnregistration(this@MainActivity) },
            )
            AnimatedVisibility(intro, exit = fadeOut(tween(450)) + scaleOut(tween(450), targetScale = 1.08f)) {
              Intro(onDone = { intro = false })
            }
          }
        }
      }
    }
    permissions.launch(arrayOf(BLUETOOTH, BLUETOOTH_CONNECT, RECORD_AUDIO))
    handleLink(intent)
  }

  override fun onNewIntent(intent: android.content.Intent) {
    super.onNewIntent(intent)
    handleLink(intent)
  }

  /** Opened from the laptop's QR code with the phone's camera app. */
  private fun handleLink(intent: android.content.Intent?) {
    intent?.dataString?.let { if (vm.gloves.connectFromLink(it)) Toast.makeText(this, "Connecting to the gloves laptop…", Toast.LENGTH_SHORT).show() }
  }

  /** Google's code scanner: its own camera screen, no camera permission for us. */
  fun scanGloveQr() {
    val options =
        com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions.Builder()
            .setBarcodeFormats(com.google.mlkit.vision.barcode.common.Barcode.FORMAT_QR_CODE)
            .build()
    com.google.mlkit.vision.codescanner.GmsBarcodeScanning.getClient(this, options)
        .startScan()
        .addOnSuccessListener { code ->
          val ok = code.rawValue?.let { vm.gloves.connectFromLink(it) } ?: false
          Toast.makeText(this, if (ok) "Connecting to the gloves laptop…" else "That isn't a Sign Talk gloves code", Toast.LENGTH_SHORT).show()
        }
        .addOnFailureListener { e -> Toast.makeText(this, "Scanner unavailable: ${e.message}", Toast.LENGTH_LONG).show() }
  }
}

// High-contrast dark palette; the yellow matches the sign line on the lens.
private val Bg = Color(0xFF0E1420)
private val Card = Color(0xFF182131)
private val CardEdge = Color(0xFF26324A)
private val Teal = Color(0xFF2EC4B6)
private val SignYellow = Color(0xFFFFD166)
private val StopRed = Color(0xFFEF476F)
private val Muted = Color(0xFF9AA8BF)

private val SignTalkColors =
    darkColorScheme(primary = Teal, onPrimary = Color(0xFF00201D), background = Bg, surface = Bg, onSurface = Color.White)

@Composable
private fun CaptionScreen(vm: CaptionViewModel, onScanQr: () -> Unit, onRegister: () -> Unit, onUnregister: () -> Unit) {
  val registration by vm.registration.collectAsStateWithLifecycle()
  val glassesStatus by vm.glasses.status.collectAsStateWithLifecycle()
  val devicesInfo by vm.glasses.devicesInfo.collectAsStateWithLifecycle()
  val previewHint by vm.glasses.previewHint.collectAsStateWithLifecycle()
  val micStatus by vm.captioner.status.collectAsStateWithLifecycle()
  val listening by vm.captioner.listening.collectAsStateWithLifecycle()
  val caption by vm.captioner.caption.collectAsStateWithLifecycle()
  val language by vm.captioner.language.collectAsStateWithLifecycle()
  val textSize by vm.glasses.textSize.collectAsStateWithLifecycle()
  val signsOn by vm.signsOn.collectAsStateWithLifecycle()
  val signVideosOn by vm.signVideosOn.collectAsStateWithLifecycle()
  val signStatus by vm.signStatus.collectAsStateWithLifecycle()
  var toolsOpen by remember { mutableStateOf(false) }
  val realGlasses by vm.glasses.useReal.collectAsStateWithLifecycle()
  val alertShowing by vm.glasses.alertShowing.collectAsStateWithLifecycle()
  val gloveHost by vm.gloves.host.collectAsStateWithLifecycle()
  val gloveStatus by vm.gloves.status.collectAsStateWithLifecycle()
  val gloveConnected by vm.gloves.connected.collectAsStateWithLifecycle()
  val gloveSigns by vm.gloves.liveSigns.collectAsStateWithLifecycle()
  val gloveSentence by vm.gloves.sentence.collectAsStateWithLifecycle()
  val gloveLaptops by vm.gloves.found.collectAsStateWithLifecycle()
  val gloveData by vm.gloves.gloveData.collectAsStateWithLifecycle()

  Column(
      Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState())
          .padding(horizontal = 18.dp, vertical = 14.dp),
      verticalArrangement = Arrangement.spacedBy(14.dp),
  ) {
    // Header
    Column(Modifier.reveal(0)) {
      Text("Sign Talk", fontSize = 30.sp, fontWeight = FontWeight.Bold, color = Color.White)
      Text("Captions and Finnish signs on your glasses", color = Muted, fontSize = 15.sp)
    }

    // Status
    Row(Modifier.reveal(1), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
      StatusChip("Glasses", glassesStatus.removePrefix("Glasses: "), ok = glassesStatus.contains("ready"))
      StatusChip("Mic", if (listening) "listening" else micStatus.removePrefix("Mic: "), ok = listening)
    }
    if (realGlasses && registration != RegistrationState.REGISTERED) {
      Button(onClick = onRegister, modifier = Modifier.fillMaxWidth().height(52.dp), shape = RoundedCornerShape(14.dp)) {
        Text("Connect to Meta AI", fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
      }
    }

    // Demo warning, mirrored on the phone while it shows on the lens
    AnimatedVisibility(alertShowing != null) {
      Box(
          Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(StopRed).padding(18.dp),
          contentAlignment = Alignment.Center,
      ) {
        Text("⚠  ${alertShowing ?: ""}", color = Color.White, fontSize = 26.sp, fontWeight = FontWeight.Bold)
      }
    }

    // Live caption
    Column(
        Modifier.reveal(2).fillMaxWidth().heightIn(min = 200.dp).clip(RoundedCornerShape(20.dp)).background(Card)
            .border(1.dp, CardEdge, RoundedCornerShape(20.dp)).padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
      Row(verticalAlignment = Alignment.CenterVertically) {
        Text("LIVE CAPTION", color = Muted, fontSize = 12.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.5.sp)
        Spacer(Modifier.weight(1f))
        Text(language.label, color = Teal, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
      }
      Text(
          caption.ifBlank { if (listening) "Listening…" else "Tap the microphone and start talking" },
          fontSize = 30.sp, lineHeight = 38.sp, fontWeight = FontWeight.Medium,
          color = if (caption.isBlank()) Muted else Color.White,
      )
      if (signsOn) {
        Text(signStatus, color = SignYellow, fontSize = 17.sp, fontWeight = FontWeight.SemiBold, lineHeight = 22.sp)
      }
    }

    // Microphone
    val micColor by animateColorAsState(if (listening) StopRed else Teal, label = "mic")
    val pulse = rememberInfiniteTransition(label = "pulse")
    val ring by pulse.animateFloat(0f, 1f, infiniteRepeatable(tween(1400, easing = FastOutSlowInEasing)), label = "ring")
    Box(Modifier.reveal(3).fillMaxWidth().padding(vertical = 4.dp), contentAlignment = Alignment.Center) {
      if (listening) {
        // a soft ring grows out of the button while the mic is live
        Box(
            Modifier.matchParentSize().graphicsLayer {
              scaleX = 1f + ring * 0.06f
              scaleY = 1f + ring * 0.35f
              alpha = (1f - ring) * 0.45f
            }.clip(RoundedCornerShape(32.dp)).background(StopRed),
        )
      }
      Button(
          onClick = { if (listening) vm.captioner.stop() else vm.captioner.start() },
          modifier = Modifier.fillMaxWidth().height(64.dp),
          shape = RoundedCornerShape(32.dp),
          colors = ButtonDefaults.buttonColors(containerColor = micColor, contentColor = Color(0xFF0B0F17)),
      ) {
        Text(if (listening) "■  Stop listening" else "●  Start listening", fontSize = 20.sp, fontWeight = FontWeight.Bold)
      }
    }

    // Settings
    Section(Modifier.reveal(4)) {
      Label("Spoken language")
      Pills(Language.entries, language, { it.label }) { vm.captioner.setLanguage(it) }
      Spacer(Modifier.height(14.dp))
      Label("Text size on the lens")
      Pills(TextSize.entries, textSize, { it.label }) { vm.glasses.setTextSize(it) }
      Spacer(Modifier.height(10.dp))
      ToggleRow("Finnish signs", "Sign names on the lens for each sentence", signsOn) { vm.setSignsOn(it) }
      ToggleRow("Sign videos", "Play the signs as one video after each sentence", signVideosOn, enabled = signsOn) {
        vm.setSignVideosOn(it)
      }
    }

    // Gloves: the wearer signs, the phone speaks for them
    Section(Modifier.reveal(5)) {
      Row(verticalAlignment = Alignment.CenterVertically) {
        Text("Gloves", color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.width(10.dp))
        Box(Modifier.size(9.dp).clip(CircleShape).background(if (gloveConnected) Teal else Color(0xFFF4A259)))
        Spacer(Modifier.width(6.dp))
        Text(gloveStatus, color = Muted, fontSize = 13.sp, maxLines = 1)
      }
      Text("Signs from the gloves, spoken out loud", color = Muted, fontSize = 13.sp)
      // what the laptop says about the glove data itself
      if (gloveConnected) {
        gloveData?.let { (text, receiving) ->
          Spacer(Modifier.height(8.dp))
          Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(9.dp).clip(CircleShape).background(
                when (receiving) { true -> Teal; false -> StopRed; null -> Muted }))
            Spacer(Modifier.width(8.dp))
            Text(text, color = if (receiving == false) StopRed else Color.White, fontSize = 14.sp, fontWeight = FontWeight.Medium)
          }
        }
      }
      Spacer(Modifier.height(12.dp))
      if (gloveSentence != null || gloveSigns.isNotEmpty()) {
        Column(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Bg).padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
          if (gloveSigns.isNotEmpty()) {
            Text(gloveSigns.joinToString("  ·  ") { it.uppercase() }, color = SignYellow, fontSize = 16.sp, fontWeight = FontWeight.Bold)
          }
          gloveSentence?.let { s ->
            val fi = language == Language.FINNISH
            Text(if (fi) s.fi else s.en, color = Color.White, fontSize = 24.sp, lineHeight = 30.sp, fontWeight = FontWeight.Medium)
            Text(if (fi) s.en else s.fi, color = Muted, fontSize = 15.sp)
          }
        }
        Spacer(Modifier.height(12.dp))
      }
      if (!gloveConnected) {
        Button(
            onClick = onScanQr, modifier = Modifier.fillMaxWidth().height(52.dp), shape = RoundedCornerShape(14.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Teal, contentColor = Color(0xFF00201D)),
        ) { Text("Scan QR on the laptop", fontSize = 17.sp, fontWeight = FontWeight.Bold) }
        Spacer(Modifier.height(12.dp))
      }
      // laptops running `signtalk-gloves run` on this Wi-Fi; tap one to pair
      if (gloveLaptops.isNotEmpty()) {
        Label("Found on this Wi-Fi")
        gloveLaptops.forEach { laptop ->
          val active = gloveConnected && laptop.host == gloveHost
          Row(
              Modifier.fillMaxWidth().padding(bottom = 8.dp).clip(RoundedCornerShape(14.dp))
                  .background(if (active) Teal.copy(alpha = 0.18f) else Bg)
                  .border(1.dp, if (active) Teal else CardEdge, RoundedCornerShape(14.dp))
                  .clickable(enabled = !active) { vm.gloves.connectTo(laptop) }.padding(horizontal = 14.dp, vertical = 12.dp),
              verticalAlignment = Alignment.CenterVertically,
          ) {
            Column(Modifier.weight(1f)) {
              Text(laptop.name, color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
              Text(laptop.host, color = Muted, fontSize = 13.sp)
            }
            Text(if (active) "Connected" else "Tap to connect", color = if (active) Teal else Muted, fontSize = 13.sp)
          }
        }
        Spacer(Modifier.height(4.dp))
      } else if (!gloveConnected) {
        Text("Looking for a laptop running signtalk-gloves… or type its address:", color = Muted, fontSize = 13.sp)
        Spacer(Modifier.height(8.dp))
      }
      Row(verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = gloveHost, onValueChange = { vm.gloves.setHost(it) }, singleLine = true,
            label = { Text("Laptop address") }, modifier = Modifier.weight(1f),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Teal, unfocusedBorderColor = CardEdge,
                focusedTextColor = Color.White, unfocusedTextColor = Color.White, focusedLabelColor = Teal, unfocusedLabelColor = Muted),
        )
        Spacer(Modifier.width(10.dp))
        Button(
            onClick = { if (gloveConnected) vm.gloves.disconnectByUser() else vm.gloves.connect() },
            shape = RoundedCornerShape(14.dp), modifier = Modifier.height(56.dp),
            colors = ButtonDefaults.buttonColors(containerColor = if (gloveConnected) CardEdge else Teal,
                contentColor = if (gloveConnected) Color.White else Color(0xFF00201D)),
        ) { Text(if (gloveConnected) "Disconnect" else "Connect", fontWeight = FontWeight.SemiBold) }
      }
      if (gloveConnected) {
        Spacer(Modifier.height(10.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
          Button(onClick = { vm.gloves.requestReplay() }, shape = RoundedCornerShape(14.dp),
              colors = ButtonDefaults.buttonColors(containerColor = SignYellow, contentColor = Color(0xFF1A1300))) {
            Text("Play glove demo", fontWeight = FontWeight.SemiBold)
          }
          if (gloveSentence != null) {
            OutlinedButton(onClick = { vm.gloves.speakAgain() }, shape = RoundedCornerShape(14.dp)) { Text("Speak again") }
          }
        }
      }
    }

    // Demo tools
    Section(Modifier.reveal(6)) {
      Row(Modifier.fillMaxWidth().clickable { toolsOpen = !toolsOpen }, verticalAlignment = Alignment.CenterVertically) {
        Text("Demo tools", color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.weight(1f))
        Text(if (toolsOpen) "▲" else "▼", color = Muted)
      }
      AnimatedVisibility(toolsOpen) {
        Column(Modifier.padding(top = 12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
          Label("Glasses")
          Pills(listOf(false, true), realGlasses, { if (it) "Real glasses" else "Simulated" }) { vm.glasses.switchTo(it) }
          previewHint?.let {
            Label("Lens preview on the laptop")
            Text(it, fontFamily = FontFamily.Monospace, fontSize = 13.sp, color = Color.White)
          }
          OutlinedButton(onClick = { vm.glasses.playVideo(TEST_VIDEO_URL) }, shape = RoundedCornerShape(12.dp)) {
            Text("Play test video on lens")
          }
          Label("Alert preview (demo: no sound detection yet)")
          Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("FIRE ALARM", "SIREN", "CAR HORN").forEach { warning ->
              Button(
                  onClick = { vm.glasses.showAlert(warning) }, shape = RoundedCornerShape(12.dp),
                  colors = ButtonDefaults.buttonColors(containerColor = StopRed, contentColor = Color.White),
              ) { Text(warning.lowercase().replaceFirstChar { it.uppercase() }, fontSize = 13.sp) }
            }
          }
          if (realGlasses) {
            Text("Meta AI: $registration", color = Muted, fontSize = 13.sp)
            Text(devicesInfo, color = Muted, fontSize = 12.sp)
            if (registration == RegistrationState.REGISTERED) {
              // The approval is tied to the glasses paired at the time; after switching glasses,
              // remove it here and connect again.
              OutlinedButton(onClick = onUnregister, shape = RoundedCornerShape(12.dp)) {
                Text("Reconnect to Meta AI (new glasses)")
              }
            }
          }
        }
      }
    }
  }
}

@Composable
private fun StatusChip(name: String, value: String, ok: Boolean) {
  Row(
      Modifier.clip(RoundedCornerShape(50)).background(Card).border(1.dp, CardEdge, RoundedCornerShape(50))
          .padding(horizontal = 12.dp, vertical = 8.dp),
      verticalAlignment = Alignment.CenterVertically,
  ) {
    Box(Modifier.size(9.dp).clip(CircleShape).background(if (ok) Teal else Color(0xFFF4A259)))
    Spacer(Modifier.width(8.dp))
    Text("$name: ", color = Muted, fontSize = 13.sp)
    Text(value, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Medium, maxLines = 1)
  }
}

@Composable
private fun Section(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
  Column(
      modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(Card)
          .border(1.dp, CardEdge, RoundedCornerShape(20.dp)).padding(18.dp),
  ) { content() }
}

@Composable
private fun Label(text: String) {
  Text(text, color = Muted, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(bottom = 8.dp))
}

@Composable
private fun <T> Pills(options: List<T>, selected: T, label: (T) -> String, onPick: (T) -> Unit) {
  Row(
      Modifier.fillMaxWidth().clip(RoundedCornerShape(50)).background(Bg).padding(4.dp),
      horizontalArrangement = Arrangement.spacedBy(4.dp),
  ) {
    options.forEach { option ->
      val on = option == selected
      Box(
          Modifier.weight(1f).clip(RoundedCornerShape(50)).background(if (on) Teal else Color.Transparent)
              .clickable { onPick(option) }.padding(vertical = 11.dp),
          contentAlignment = Alignment.Center,
      ) {
        Text(label(option), color = if (on) Color(0xFF00201D) else Color.White,
            fontWeight = if (on) FontWeight.Bold else FontWeight.Normal, fontSize = 15.sp)
      }
    }
  }
}

@Composable
private fun ToggleRow(title: String, detail: String, on: Boolean, enabled: Boolean = true, onChange: (Boolean) -> Unit) {
  Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
    Column(Modifier.weight(1f)) {
      Text(title, color = if (enabled) Color.White else Muted, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
      Text(detail, color = Muted, fontSize = 13.sp)
    }
    Switch(
        checked = on && enabled, onCheckedChange = onChange, enabled = enabled,
        colors = SwitchDefaults.colors(checkedTrackColor = Teal, checkedThumbColor = Color.White),
    )
  }
}

private const val INTRO_MS = 2600L

/** Slides a section up into place after the intro, one after another. */
@Composable
private fun Modifier.reveal(order: Int): Modifier {
  val shown = remember { Animatable(0f) }
  LaunchedEffect(Unit) {
    delay(INTRO_MS + 120L + order * 90L)
    shown.animateTo(1f, tween(500, easing = FastOutSlowInEasing))
  }
  return graphicsLayer {
    alpha = shown.value
    translationY = (1f - shown.value) * 70f
  }
}

/** Opening animation: sound bars, the name, then the idea in three steps. Tap to skip. */
@Composable
private fun Intro(onDone: () -> Unit) {
  val title = remember { Animatable(0f) }
  val steps = List(3) { remember { Animatable(0f) } }
  LaunchedEffect(Unit) {
    title.animateTo(1f, tween(600, easing = FastOutSlowInEasing))
    steps.forEach {
      delay(180)
      it.animateTo(1f, tween(380, easing = FastOutSlowInEasing))
    }
    delay(INTRO_MS - 600 - 3 * 560)
    onDone()
  }
  val wave = rememberInfiniteTransition(label = "wave")
  val phase by wave.animateFloat(0f, 6.2832f, infiniteRepeatable(tween(1100), RepeatMode.Restart), label = "phase")

  Box(Modifier.fillMaxSize().background(Bg).clickable { onDone() }, contentAlignment = Alignment.Center) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
      // sound bars: speech coming in
      Row(Modifier.height(90.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
        repeat(7) { i ->
          val h = 0.35f + 0.65f * ((kotlin.math.sin(phase + i * 0.9f) + 1f) / 2f)
          val colour = if (i < 3) Teal else if (i == 3) Color.White else SignYellow
          Box(Modifier.width(9.dp).height((90 * h).dp).clip(RoundedCornerShape(50)).background(colour))
        }
      }
      Spacer(Modifier.height(28.dp))
      Text(
          "Sign Talk", fontSize = 44.sp, fontWeight = FontWeight.Bold, color = Color.White,
          modifier = Modifier.graphicsLayer {
            alpha = title.value
            scaleX = 0.85f + 0.15f * title.value
            scaleY = 0.85f + 0.15f * title.value
          },
      )
      Spacer(Modifier.height(18.dp))
      Row(verticalAlignment = Alignment.CenterVertically) {
        val words = listOf("Speech" to Teal, "Captions" to Color.White, "Signs" to SignYellow)
        words.forEachIndexed { i, (word, colour) ->
          val v = steps[i].value
          if (i > 0) Text("  →  ", color = Muted.copy(alpha = v), fontSize = 18.sp)
          Text(
              word, color = colour, fontSize = 20.sp, fontWeight = FontWeight.SemiBold,
              modifier = Modifier.graphicsLayer { alpha = v; translationY = (1f - v) * 24f },
          )
        }
      }
      Spacer(Modifier.height(10.dp))
      Text("so everyone can join the conversation", color = Muted.copy(alpha = steps[2].value), fontSize = 14.sp)
    }
  }
}
