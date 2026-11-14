package com.signtalk.app

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

private const val TAG = "SignTalkCaptioner"

/**
 * Phone microphone -> Android speech-to-text. Android's recogniser stops after each
 * sentence or pause, so we restart it straight away to get continuous captions.
 * Must be used from the main thread.
 */
class Captioner(private val context: Context) {

  private val _caption = MutableStateFlow("")
  /** The last few finished sentences plus whatever is being said right now. */
  val caption: StateFlow<String> = _caption.asStateFlow()

  private val _sentences = MutableSharedFlow<Pair<String, Language>>(extraBufferCapacity = 8)
  /** Each finished sentence with its language (not the partial words), e.g. for the sign finder. */
  val sentences: SharedFlow<Pair<String, Language>> = _sentences.asSharedFlow()

  private val _status = MutableStateFlow("Mic: off")
  val status: StateFlow<String> = _status.asStateFlow()

  private val _listening = MutableStateFlow(false)
  val listening: StateFlow<Boolean> = _listening.asStateFlow()

  private val handler = Handler(Looper.getMainLooper())
  private var permissionErrors = 0
  private var recognizer: SpeechRecognizer? = null
  private val transcript = Transcript()

  private val _language = MutableStateFlow(Language.ENGLISH)
  /** Which language the recogniser listens for. It understands one at a time. */
  val language: StateFlow<Language> = _language.asStateFlow()

  private fun intent() =
      Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, _language.value.tag)
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true) // words appear while speaking
        putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
      }

  /** Switch language; takes effect straight away if the microphone is on. */
  fun setLanguage(language: Language) {
    if (language == _language.value) return
    _language.value = language
    if (_listening.value) {
      recognizer?.cancel()
      restart(0)
    }
  }

  fun start() {
    if (_listening.value) return
    if (!SpeechRecognizer.isRecognitionAvailable(context)) {
      _status.value = "Mic: no speech service on this phone"
      return
    }
    recognizer =
        SpeechRecognizer.createSpeechRecognizer(context).apply { setRecognitionListener(listener) }
    _listening.value = true
    listen()
  }

  fun stop() {
    _listening.value = false
    handler.removeCallbacksAndMessages(null)
    recognizer?.destroy()
    recognizer = null
    _status.value = "Mic: off"
  }

  private fun listen() {
    if (_listening.value) recognizer?.startListening(intent())
  }

  private fun restart(delayMs: Long) {
    handler.removeCallbacksAndMessages(null)
    handler.postDelayed(::listen, delayMs)
  }

  private val listener =
      object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
          permissionErrors = 0
          _status.value = "Mic: listening"
        }

        override fun onPartialResults(partialResults: Bundle?) {
          val text = partialResults.bestText() ?: return
          _caption.value = transcript.partial(text)
        }

        override fun onResults(results: Bundle?) {
          val sentence = results.bestText().orEmpty()
          _caption.value = transcript.final(sentence)
          if (sentence.isNotBlank()) _sentences.tryEmit(sentence to _language.value)
          restart(0)
        }

        override fun onError(error: Int) {
          Log.d(TAG, "Recogniser error $error")
          when (error) {
            // Nobody spoke: just listen again.
            SpeechRecognizer.ERROR_NO_MATCH,
            SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> restart(0)
            SpeechRecognizer.ERROR_RECOGNIZER_BUSY,
            SpeechRecognizer.ERROR_CLIENT -> {
              recognizer?.cancel()
              restart(300)
            }
            // Google's service sometimes reports this once and then works on the next try;
            // give up only if it keeps happening.
            SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> {
              permissionErrors++
              if (permissionErrors > 5) {
                stop()
                _status.value = "Mic: permission denied"
              } else {
                recognizer?.cancel()
                restart(500)
              }
            }
            else -> {
              _status.value = "Mic: error $error, retrying"
              restart(500)
            }
          }
        }

        override fun onBeginningOfSpeech() {}

        override fun onRmsChanged(rmsdB: Float) {}

        override fun onBufferReceived(buffer: ByteArray?) {}

        override fun onEndOfSpeech() {}

        override fun onEvent(eventType: Int, params: Bundle?) {}
      }

  private fun Bundle?.bestText(): String? =
      this?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
}

enum class Language(val tag: String, val label: String) {
  ENGLISH("en-US", "English"),
  FINNISH("fi-FI", "Suomi"),
}
