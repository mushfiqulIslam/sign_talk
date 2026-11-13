package com.signtalk.app

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.meta.wearable.dat.core.Wearables
import kotlinx.coroutines.launch

/** Wires the microphone captions to the glasses lens. */
class CaptionViewModel(app: Application) : AndroidViewModel(app) {

  val glasses = GlassesLink(app, viewModelScope)
  val captioner = Captioner(app)
  private var started = false

  init {
    viewModelScope.launch { captioner.caption.collect { glasses.show(it) } }
  }

  /** Call once the Bluetooth and microphone permissions are granted. */
  fun startAll() {
    if (started) return
    started = true
    Wearables.initialize(getApplication())
        .onFailure { e, _ -> Log.e("SignTalk", "Wearables init failed: ${e.description}") }
    glasses.connectMockGlasses()
    captioner.start()
  }

  override fun onCleared() {
    captioner.stop()
    glasses.disconnect()
    super.onCleared()
  }
}
