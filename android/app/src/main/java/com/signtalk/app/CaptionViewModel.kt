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
import kotlinx.coroutines.flow.conflate
import kotlinx.coroutines.launch

/** Wires the microphone captions to the glasses lens. */
class CaptionViewModel(app: Application) : AndroidViewModel(app) {

  val glasses = GlassesLink(app, viewModelScope)
  val captioner = Captioner(app)
  private var started = false
  val gloves = GloveLink(app, viewModelScope)
  private var micPausedForSpeech = false
  private val signClient = SignClient(BuildConfig.SIGN_API_URL, BuildConfig.SIGN_API_KEY)

  private val _signsOn = MutableStateFlow(false)
  /** Off by default: with signs off or the API unreachable, the app behaves exactly as before. */
  val signsOn: StateFlow<Boolean> = _signsOn.asStateFlow()

  private val _signVideosOn = MutableStateFlow(false)
  /** Also play the Signbank clips on the lens (full screen, one after another). */
  val signVideosOn: StateFlow<Boolean> = _signVideosOn.asStateFlow()

  private val _signStatus = MutableStateFlow(if (signClient.configured) "Signs: off" else "Signs: no API address in .env")
  val signStatus: StateFlow<String> = _signStatus.asStateFlow()

  fun setSignsOn(on: Boolean) {
    _signsOn.value = on
    _signStatus.value = if (on) "Signs: waiting for a sentence" else "Signs: off"
  }

  fun setSignVideosOn(on: Boolean) {
    _signVideosOn.value = on
  }

  // The toolkit can't be asked anything before Wearables.initialize(), so the screen reads
  // this copy instead, which starts following the toolkit once it is initialised.
  private val _registration = MutableStateFlow(RegistrationState.UNAVAILABLE)
  val registration: StateFlow<RegistrationState> = _registration.asStateFlow()

  init {
    viewModelScope.launch { captioner.caption.collect { glasses.show(it) } }
    // Speak glove sentences in the language picked on screen; pause the caption mic meanwhile
    // so the app doesn't caption its own voice.
    gloves.startDiscovery()
    gloves.finnish = { captioner.language.value == Language.FINNISH }
    gloves.onSpeaking = { speaking ->
      if (speaking && captioner.listening.value) {
        micPausedForSpeech = true
        captioner.stop()
      } else if (!speaking && micPausedForSpeech) {
        micPausedForSpeech = false
        captioner.start()
      }
    }
    // Each finished sentence -> sign API -> sign names (and clips) on the lens. While one sentence's
    // clips play, only the newest waiting sentence is kept, so the lens never falls far behind.
    viewModelScope.launch {
      captioner.sentences.conflate().collect { (text, language) ->
        if (!_signsOn.value) return@collect
        _signStatus.value = "Signs: asking…"
        val result = signClient.signs(text, language)
        if (result == null) {
          _signStatus.value = "Signs: API not reachable, captions only"
          return@collect
        }
        _signStatus.value =
            "Signs (${result.ms} ms): ${result.signs.joinToString(" ")}" +
                if (result.dropped.isNotEmpty()) "  (not in Signbank: ${result.dropped.joinToString(" ")})" else ""
        glasses.showSigns(result.signs)
        if (_signVideosOn.value) {
          val single = result.sentenceVideo
          if (single != null) {
            glasses.playVideos(listOf(single)) // one joined video: no gaps between signs
          } else {
            // fallback: Signbank clips one by one; the lens stalls on the same clip twice in a row
            val clips = result.videos.filterNotNull()
            glasses.playVideos(clips.filterIndexed { i, c -> i == 0 || c != clips[i - 1] })
          }
        }
      }
    }
  }

  /**
   * Call once the Bluetooth and microphone permissions are granted. Real or simulated glasses:
   * whichever was last picked in Demo tools.
   */
  fun startAll() {
    if (started) return
    started = true
    Wearables.initialize(getApplication())
        .onFailure { e, _ -> Log.e("SignTalk", "Wearables init failed: ${e.description}") }
    viewModelScope.launch { Wearables.registrationState.collect { _registration.value = it } }
    glasses.connectChosen()
    captioner.start()
  }

  override fun onCleared() {
    captioner.stop()
    gloves.close()
    glasses.disconnect()
    super.onCleared()
  }
}
