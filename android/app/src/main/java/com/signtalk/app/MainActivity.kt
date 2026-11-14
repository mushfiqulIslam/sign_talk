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
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.meta.wearable.dat.core.Wearables
import com.meta.wearable.dat.core.types.RegistrationState

/** true = the real Ray-Ban Display glasses; false = Meta's mock glasses shown in Chrome. */
private const val USE_REAL_GLASSES = false

/** Meta's own small test clip (266 x 150), already within the lens video limits. */
private const val TEST_VIDEO_URL =
    "https://raw.githubusercontent.com/facebook/meta-wearables-dat-android/refs/heads/assets/video_266x150_faststart.mp4"

class MainActivity : ComponentActivity() {

  private val vm: CaptionViewModel by viewModels()

  private val permissions =
      registerForActivityResult(RequestMultiplePermissions()) { results ->
        if (results.values.all { it }) {
          vm.startAll(USE_REAL_GLASSES)
        } else {
          Toast.makeText(this, "Bluetooth and microphone permissions are needed", Toast.LENGTH_LONG)
              .show()
        }
      }

  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    setContent {
      MaterialTheme {
        Surface(Modifier.fillMaxSize()) {
          CaptionScreen(
              vm,
              onRegister = { Wearables.startRegistration(this) },
              onUnregister = { Wearables.startUnregistration(this) },
          )
        }
      }
    }
    permissions.launch(arrayOf(BLUETOOTH, BLUETOOTH_CONNECT, RECORD_AUDIO))
  }
}

@Composable
private fun CaptionScreen(vm: CaptionViewModel, onRegister: () -> Unit, onUnregister: () -> Unit) {
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

  Column(Modifier.fillMaxSize().safeDrawingPadding().padding(20.dp)) {
    Text("Sign Talk", style = MaterialTheme.typography.headlineMedium)
    Spacer(Modifier.height(8.dp))
    Text(glassesStatus)
    Text(micStatus)
    if (USE_REAL_GLASSES) {
      Text("Meta AI: $registration")
      Text(devicesInfo, fontSize = 12.sp)
      if (registration != RegistrationState.REGISTERED) {
        Spacer(Modifier.height(8.dp))
        Button(onClick = onRegister) { Text("Connect to Meta AI") }
      } else {
        // The approval is tied to the glasses paired at the time; after switching glasses,
        // remove it here and tap "Connect to Meta AI" again.
        Spacer(Modifier.height(8.dp))
        OutlinedButton(onClick = onUnregister) { Text("Reconnect to Meta AI (new glasses)") }
      }
    }
    previewHint?.let {
      Spacer(Modifier.height(8.dp))
      Text("Lens preview on laptop:", style = MaterialTheme.typography.labelMedium)
      Text(it, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
    }
    Spacer(Modifier.height(16.dp))
    Button(onClick = { if (listening) vm.captioner.stop() else vm.captioner.start() }) {
      Text(if (listening) "Stop microphone" else "Start microphone")
    }
    Spacer(Modifier.height(8.dp))
    Row {
      Language.entries.forEach { lang ->
        if (lang == language) {
          Button(onClick = {}) { Text(lang.label) }
        } else {
          OutlinedButton(onClick = { vm.captioner.setLanguage(lang) }) { Text(lang.label) }
        }
        Spacer(Modifier.width(8.dp))
      }
    }
    Spacer(Modifier.height(8.dp))
    Row {
      TextSize.entries.forEach { size ->
        if (size == textSize) {
          Button(onClick = {}) { Text(size.label) }
        } else {
          OutlinedButton(onClick = { vm.glasses.setTextSize(size) }) { Text(size.label) }
        }
        Spacer(Modifier.width(6.dp))
      }
    }
    Spacer(Modifier.height(8.dp))
    OutlinedButton(onClick = { vm.glasses.playVideo(TEST_VIDEO_URL) }) { Text("Test video on lens") }
    Spacer(Modifier.height(8.dp))
    Row {
      if (signsOn) Button(onClick = { vm.setSignsOn(false) }) { Text("FinSL signs: on") }
      else OutlinedButton(onClick = { vm.setSignsOn(true) }) { Text("FinSL signs: off") }
      Spacer(Modifier.width(6.dp))
      if (signVideosOn) Button(onClick = { vm.setSignVideosOn(false) }) { Text("Sign videos: on") }
      else OutlinedButton(onClick = { vm.setSignVideosOn(true) }) { Text("Sign videos: off") }
    }
    Text(signStatus)
    Spacer(Modifier.height(24.dp))
    Text(caption.ifBlank { "Say something…" }, fontSize = 28.sp, lineHeight = 34.sp)
  }
}
