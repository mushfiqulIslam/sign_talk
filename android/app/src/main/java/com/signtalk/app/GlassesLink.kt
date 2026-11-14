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
import com.meta.wearable.dat.display.types.VideoCodec
import com.meta.wearable.dat.display.types.VideoPlayerState
import com.meta.wearable.dat.display.types.VideoSource
import com.meta.wearable.dat.display.views.Direction
import com.meta.wearable.dat.display.views.ImageSize
import com.meta.wearable.dat.display.views.TextStyle
import com.meta.wearable.dat.display.views.VideoPlayer
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
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeoutOrNull

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

  private val _textSize = MutableStateFlow(TextSize.EXTRA_LARGE)
  val textSize: StateFlow<TextSize> = _textSize.asStateFlow()

  fun setTextSize(size: TextSize) {
    _textSize.value = size
  }

  /** While a video plays, captions are not redrawn (the video player is full screen). */
  private val videoPlaying = MutableStateFlow(false)

  /** One send to the glasses at a time, so a slow caption can't land on top of a video. */
  private val sendLock = Mutex()

  private val errors = CoroutineExceptionHandler { _, t ->
    Log.e(TAG, "Glasses error", t)
    _status.value = "Glasses error: ${t.message}"
  }

  init {
    // Redraw the lens whenever the caption or the display changes. StateFlow drops
    // intermediate values while a send is in progress, so we always show the newest text.
    scope.launch(Dispatchers.IO + errors) {
      combine(display, caption, _textSize, videoPlaying) { d, text, size, playing ->
            Triple(d.takeUnless { playing }, text, size)
          }
          .collect { (d, text, size) ->
            if (d != null) {
              draw(d, text, size)
              // keep Bluetooth traffic reasonable while words stream in; pictures are bigger
              delay(if (size == TextSize.EXTRA_LARGE) 250 else 60)
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
    watchDevices()
    scope.launch(errors) {
      if (Wearables.registrationState.value != RegistrationState.REGISTERED) {
        _status.value = "Glasses: tap \"Connect to Meta AI\" and approve in the Meta AI app"
      }
      Wearables.registrationState.first { it == RegistrationState.REGISTERED }
      startSession(AutoDeviceSelector(filter = { it.isDisplayCapable() }))
    }
  }

  private val _devicesInfo = MutableStateFlow("Toolkit sees: nothing yet")
  /** What the toolkit knows about each pair of glasses; helps explain "No eligible device". */
  val devicesInfo: StateFlow<String> = _devicesInfo.asStateFlow()
  private val deviceLines = mutableMapOf<String, String>()
  private var watchingDevices = false

  private fun watchDevices() {
    if (watchingDevices) return
    watchingDevices = true
    scope.launch(errors) {
      Wearables.devices.collect { ids ->
        Log.i(TAG, "Toolkit device list: ${ids.size} device(s): $ids")
        if (ids.isEmpty()) _devicesInfo.value = "Toolkit sees: no glasses"
        for (id in ids) {
          scope.launch(errors) {
            Wearables.devicesMetadata[id]?.collect { d ->
              val line =
                  "${d.name}: link=${d.linkState}, compatibility=${d.compatibility}, " +
                      "display=${d.isDisplayCapable()}"
              Log.i(TAG, "Device $id -> $line")
              synchronized(deviceLines) {
                deviceLines[id.toString()] = line
                _devicesInfo.value = "Toolkit sees:\n" + deviceLines.values.joinToString("\n")
              }
            }
          }
        }
      }
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

  private suspend fun draw(d: Display, text: String, size: TextSize) = sendLock.withLock {
    if (videoPlaying.value) return@withLock // a video started while we waited
    val result =
        when (size) {
          // Drawn as a picture: bigger than any built-in text style.
          TextSize.EXTRA_LARGE -> {
            val bitmap = TextBitmap.render(lastWords(text, 120).ifBlank { "Listening…" })
            d.sendContent {
              flexBox(direction = Direction.COLUMN) { image(bitmap = bitmap, sizePreset = ImageSize.FILL) }
            }
          }
          else -> {
            val large = size == TextSize.LARGE
            // Large text fits roughly half as many characters on the lens.
            val shown = lastWords(text, if (large) 70 else 140).ifBlank { "Listening…" }
            d.sendContent {
              flexBox(direction = Direction.COLUMN, padding = 24) {
                text(shown, style = if (large) TextStyle.HEADING else TextStyle.BODY)
              }
            }
          }
        }
    result.onFailure { e, _ -> Log.w(TAG, "Send failed: ${e.description}") }
  }

  /**
   * Plays one MP4 full screen on the lens, then goes back to captions.
   * Meta's limits: https only, MP4, at most 400 px per side and 70,000 pixels in total.
   */
  fun playVideo(url: String) {
    val d = display.value
    if (d == null) {
      _status.value = "Glasses: lens not ready for video"
      return
    }
    if (videoPlaying.value) return
    scope.launch(Dispatchers.IO + errors) {
      videoPlaying.value = true
      val player = VideoPlayer(source = VideoSource.Url(url), codec = VideoCodec.MP4)
      try {
        // Waits for any caption still on its way, then shows the video player.
        sendLock.withLock {
          d.sendContent { video(player = player) }
              .onFailure { e, _ -> Log.w(TAG, "Video send failed: ${e.description}") }
        }
        val stateLog = scope.launch { player.state.collect { Log.i(TAG, "Video state: $it") } }
        val errorLog = scope.launch { player.error.collect { if (it != null) Log.w(TAG, "Video error: $it") } }
        player.play()
        _status.value = "Glasses: playing video…"
        val started = System.currentTimeMillis()
        val result =
            withTimeoutOrNull(60_000) {
              combine(player.state, player.error) { state, error -> state to error }
                  .first { (state, error) -> error != null || state == VideoPlayerState.ENDED }
            }
        val seconds = (System.currentTimeMillis() - started) / 1000.0
        Log.i(TAG, "Video done after ${seconds}s: $result")
        _status.value =
            when {
              result == null -> "Glasses: video timed out"
              result.second != null -> "Glasses: video error ${result.second}"
              else -> "Glasses: video played (${"%.1f".format(seconds)} s)"
            }
        stateLog.cancel()
        errorLog.cancel()
      } finally {
        player.close()
        videoPlaying.value = false // captions come back
      }
    }
  }

  /** The lens is small: keep only the end of the text, cut at a word boundary. */
  private fun lastWords(text: String, maxChars: Int): String {
    if (text.length <= maxChars) return text
    val tail = text.takeLast(maxChars)
    val space = tail.indexOf(' ')
    return "…" + if (space in 0 until 30) tail.substring(space + 1) else tail
  }
}

enum class TextSize(val label: String) {
  NORMAL("Normal"),
  LARGE("Large"),
  EXTRA_LARGE("Extra large"),
}
