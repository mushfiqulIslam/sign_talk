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
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

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
    setContent { MaterialTheme { Surface(Modifier.fillMaxSize()) { CaptionScreen(vm) } } }
    permissions.launch(arrayOf(BLUETOOTH, BLUETOOTH_CONNECT, RECORD_AUDIO))
  }
}

@Composable
private fun CaptionScreen(vm: CaptionViewModel) {
  val glassesStatus by vm.glasses.status.collectAsStateWithLifecycle()
  val previewHint by vm.glasses.previewHint.collectAsStateWithLifecycle()
  val micStatus by vm.captioner.status.collectAsStateWithLifecycle()
  val listening by vm.captioner.listening.collectAsStateWithLifecycle()
  val caption by vm.captioner.caption.collectAsStateWithLifecycle()

  Column(Modifier.fillMaxSize().safeDrawingPadding().padding(20.dp)) {
    Text("Sign Talk", style = MaterialTheme.typography.headlineMedium)
    Spacer(Modifier.height(8.dp))
    Text(glassesStatus)
    Text(micStatus)
    previewHint?.let {
      Spacer(Modifier.height(8.dp))
      Text("Lens preview on laptop:", style = MaterialTheme.typography.labelMedium)
      Text(it, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
    }
    Spacer(Modifier.height(16.dp))
    Button(onClick = { if (listening) vm.captioner.stop() else vm.captioner.start() }) {
      Text(if (listening) "Stop microphone" else "Start microphone")
    }
    Spacer(Modifier.height(24.dp))
    Text(caption.ifBlank { "Say something…" }, fontSize = 28.sp, lineHeight = 34.sp)
  }
}
