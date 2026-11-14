package com.signtalk.app

import android.content.Context
import android.util.Log
import com.meta.wearable.dat.core.Wearables
import com.meta.wearable.dat.core.selectors.AutoDeviceSelector
import com.meta.wearable.dat.core.selectors.DeviceSelector
import com.meta.wearable.dat.core.selectors.SpecificDeviceSelector
import com.meta.wearable.dat.core.session.DeviceSession
import com.meta.wearable.dat.core.session.DeviceSessionState
import com.meta.wearable.dat.core.types.RegistrationState
import com.meta.wearable.dat.display.Display
import com.meta.wearable.dat.display.addDisplay
import com.meta.wearable.dat.display.removeDisplay
import com.meta.wearable.dat.display.types.DisplayState
import com.meta.wearable.dat.display.views.Direction
import com.meta.wearable.dat.display.views.TextStyle
import com.meta.wearable.dat.mockdevice.MockDeviceKit
import com.meta.wearable.dat.mockdevice.api.GlassesModel
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

private const val TAG = "SignTalkGlasses"
private const val PREVIEW_PORT = 9000

/**
 * Everything to do with the glasses: pairing the mock glasses, opening a session,
 * attaching the display and drawing caption text on the lens.
 */
class GlassesLink(private val context: Context, private val scope: CoroutineScope) {

  private val _status = MutableStateFlow("Glasses: not connected")
  val status: StateFlow<String> = _status.asStateFlow()

  private val _previewHint = MutableStateFlow<String?>(null)
  val previewHint: StateFlow<String?> = _previewHint.asStateFlow()

  private val display = MutableStateFlow<Display?>(null)
  private val caption = MutableStateFlow("")
  private var session: DeviceSession? = null

  private val errors = CoroutineExceptionHandler { _, t ->
    Log.e(TAG, "Glasses error", t)
    _status.value = "Glasses error: ${t.message}"
  }

  init {
    // Redraw the lens whenever the caption or the display changes. StateFlow drops
    // intermediate values while a send is in progress, so we always show the newest text.
    scope.launch(Dispatchers.IO + errors) {
      combine(display, caption) { d, text -> d to text }
          .collect { (d, text) ->
            if (d != null) {
              draw(d, text)
              delay(60) // keep Bluetooth traffic reasonable while words stream in
            }
          }
    }
  }

  /** Version 1: Meta's simulated Ray-Ban Display glasses, lens viewable in Chrome. */
  fun connectMockGlasses() {
    if (session != null) return
    val kit = MockDeviceKit.getInstance(context)
    kit.enable()
    kit.pairGlasses(GlassesModel.META_RAYBAN_DISPLAY)
        .fold(
            onSuccess = { glasses ->
              glasses.powerOn()
              glasses.don()
              kit.startTestServer(PREVIEW_PORT)
                  .fold(
                      onSuccess = { port ->
                        _previewHint.value =
                            "adb forward tcp:$port tcp:$port\nthen open http://127.0.0.1:$port/"
                      },
                      onFailure = { e, _ -> Log.w(TAG, "Preview server failed: ${e.description}") },
                  )
              // The guide says: only open a session once registered. The mock kit
              // registers us itself, but possibly a moment after enable().
              scope.launch(errors) {
                _status.value = "Glasses: waiting for registration…"
                Wearables.registrationState.first { it == RegistrationState.REGISTERED }
                startSession(SpecificDeviceSelector(glasses.deviceIdentifier))
              }
            },
            onFailure = { e, _ -> _status.value = "Mock glasses failed: ${e.description}" },
        )
  }

  /**
   * Real Meta Ray-Ban Display glasses, paired through the Meta AI app. Waits until the
   * app is registered with Meta AI (see [MainActivity]), then uses whichever connected
   * glasses have a display.
   */
  fun connectRealGlasses() {
    if (session != null) return
    scope.launch(errors) {
      if (Wearables.registrationState.value != RegistrationState.REGISTERED) {
        _status.value = "Glasses: tap \"Connect to Meta AI\" and approve in the Meta AI app"
      }
      Wearables.registrationState.first { it == RegistrationState.REGISTERED }
      startSession(AutoDeviceSelector(filter = { it.isDisplayCapable() }))
    }
  }

  /** Close the display, then the session (the order Meta's guide asks for). */
  fun disconnect() {
    display.value = null
    session?.let { s ->
      s.removeDisplay().onFailure { e, _ -> Log.w(TAG, "removeDisplay failed: ${e.description}") }
      s.stop()
    }
    session = null
    _status.value = "Glasses: not connected"
  }

  fun show(text: String) {
    caption.value = text
  }

  private fun startSession(selector: DeviceSelector) {
    _status.value = "Glasses: starting session…"
    Wearables.createSession(selector)
        .fold(
            onSuccess = { s ->
              session = s
              scope.launch(errors) {
                s.errors.collect { e -> _status.value = "Session error: ${e.description}" }
              }
              scope.launch(errors) {
                s.state.collect { state ->
                  when (state) {
                    DeviceSessionState.STARTED -> if (display.value == null) attachDisplay(s)
                    // A stopped session can't be reused: forget it so we can connect again.
                    DeviceSessionState.STOPPED -> {
                      if (session === s) session = null
                      display.value = null
                      _status.value = "Glasses: session stopped"
                    }
                    else -> {}
                  }
                }
              }
              s.start()
            },
            onFailure = { e, _ ->
              _status.value = "Glasses: not found yet (${e.description}), retrying…"
              Log.w(TAG, "createSession failed: ${e.description}")
              // Right after registration the toolkit may not have listed the glasses yet.
              scope.launch(errors) {
                delay(2000)
                if (session == null) startSession(selector)
              }
            },
        )
  }

  private fun attachDisplay(s: DeviceSession) {
    _status.value = "Glasses: attaching display…"
    s.addDisplay()
        .fold(
            onSuccess = { d ->
              scope.launch(errors) {
                d.state.collect { state ->
                  Log.i(TAG, "Display state: $state")
                  when (state) {
                    DisplayState.STARTED -> {
                      _status.value = "Glasses: lens ready"
                      display.value = d
                    }
                    DisplayState.STOPPED -> {
                      _status.value = "Glasses: display stopped"
                      display.value = null
                    }
                    else -> {}
                  }
                }
              }
            },
            onFailure = { e, _ -> _status.value = "Display failed: ${e.description}" },
        )
  }

  private suspend fun draw(d: Display, text: String) {
    val shown = lastWords(text, 140).ifBlank { "Listening…" }
    d.sendContent {
          flexBox(direction = Direction.COLUMN, padding = 24) {
            text(shown, style = TextStyle.BODY)
          }
        }
        .onFailure { e, _ -> Log.w(TAG, "Send failed: ${e.description}") }
  }

  /** The lens is small: keep only the end of the text, cut at a word boundary. */
  private fun lastWords(text: String, maxChars: Int): String {
    if (text.length <= maxChars) return text
    val tail = text.takeLast(maxChars)
    val space = tail.indexOf(' ')
    return "…" + if (space in 0 until 30) tail.substring(space + 1) else tail
  }
}
