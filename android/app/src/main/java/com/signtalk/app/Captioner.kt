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
import kotlinx.coroutines.flow.MutableStateFlow
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

  private val _status = MutableStateFlow("Mic: off")
  val status: StateFlow<String> = _status.asStateFlow()

  private val _listening = MutableStateFlow(false)
  val listening: StateFlow<Boolean> = _listening.asStateFlow()

  private val handler = Handler(Looper.getMainLooper())
  private var recognizer: SpeechRecognizer? = null
  private val finished = ArrayDeque<String>()

  private val intent =
      Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true) // words appear while speaking
        putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
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
    if (_listening.value) recognizer?.startListening(intent)
  }

  private fun restart(delayMs: Long) {
    handler.removeCallbacksAndMessages(null)
    handler.postDelayed(::listen, delayMs)
  }

  private fun publish(current: String) {
    _caption.value = (finished + current).filter { it.isNotBlank() }.joinToString(" ")
  }

  private val listener =
      object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
          _status.value = "Mic: listening"
        }

        override fun onPartialResults(partialResults: Bundle?) {
          val text = partialResults.bestText() ?: return
          publish(text)
        }

        override fun onResults(results: Bundle?) {
          results.bestText()?.takeIf { it.isNotBlank() }?.let {
            finished.addLast(it)
            while (finished.size > 3) finished.removeFirst()
          }
          publish("")
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
            SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> {
              stop()
              _status.value = "Mic: permission denied"
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
