package com.signtalk.app

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.meta.wearable.dat.core.Wearables
import com.meta.wearable.dat.core.types.RegistrationState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** Wires the microphone captions to the glasses lens. */
class CaptionViewModel(app: Application) : AndroidViewModel(app) {

  val glasses = GlassesLink(app, viewModelScope)
  val captioner = Captioner(app)
  private var started = false

  // The toolkit can't be asked anything before Wearables.initialize(), so the screen reads
  // this copy instead, which starts following the toolkit once it is initialised.
  private val _registration = MutableStateFlow(RegistrationState.UNAVAILABLE)
  val registration: StateFlow<RegistrationState> = _registration.asStateFlow()

  init {
    viewModelScope.launch { captioner.caption.collect { glasses.show(it) } }
  }

  /**
   * Call once the Bluetooth and microphone permissions are granted.
   * [useRealGlasses] false = Meta's simulated glasses, lens viewed in Chrome.
   */
  fun startAll(useRealGlasses: Boolean) {
    if (started) return
    started = true
    Wearables.initialize(getApplication())
        .onFailure { e, _ -> Log.e("SignTalk", "Wearables init failed: ${e.description}") }
    viewModelScope.launch { Wearables.registrationState.collect { _registration.value = it } }
    if (useRealGlasses) glasses.connectRealGlasses() else glasses.connectMockGlasses()
    captioner.start()
  }

  override fun onCleared() {
    captioner.stop()
    glasses.disconnect()
    super.onCleared()
  }
}
