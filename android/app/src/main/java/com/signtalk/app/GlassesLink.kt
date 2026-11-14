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
import kotlinx.coroutines.Job
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

  /** FinSL sign names for the last sentence, shown above the caption for a few seconds. */
  private val signsLine = MutableStateFlow<String?>(null)

  /** Demo-only warning (no sound detection): drawn over everything for a few seconds. */
  private val alert = MutableStateFlow<String?>(null)
  val alertShowing: StateFlow<String?> = alert.asStateFlow()
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
      combine(display, caption, _textSize, videoPlaying, signsLine) { d, text, size, playing, signs ->
            Frame(d, text, size, signs, playing)
          }
          .combine(alert) { f, a -> f.copy(alert = a) }
          .collect { f ->
            // while a video plays it owns the (full-screen) lens; a warning beats even a video
            val d = f.display?.takeUnless { f.playing && f.alert == null }
            if (d != null) {
              draw(d, f.text, f.size, f.signs, f.alert)
              // keep Bluetooth traffic reasonable while words stream in; pictures are bigger
              delay(if (f.size == TextSize.EXTRA_LARGE) 250 else 60)
            }
          }
    }
  }

  private val prefs = context.getSharedPreferences("glasses", Context.MODE_PRIVATE)
  private val _useReal = MutableStateFlow(prefs.getBoolean("real", false))
  /** true = real Ray-Ban Display glasses, false = Meta's simulated glasses (lens in Chrome). */
  val useReal: StateFlow<Boolean> = _useReal.asStateFlow()

  /** Bumped on every switch, so waits and retries from the previous kind of glasses stop. */
  @Volatile private var generation = 0
  private var reconnects = 0
  private var connectJob: Job? = null
  private var mockOn = false
  private var mockId: com.meta.wearable.dat.core.types.DeviceIdentifier? = null

  /** Connects to whichever kind of glasses was last chosen. */
  fun connectChosen() = if (_useReal.value) connectRealGlasses() else connectMockGlasses()

  /** Switch between real and simulated glasses on the fly (Demo tools). */
  fun switchTo(real: Boolean) {
    if (real == _useReal.value && session != null) return
    _useReal.value = real
    prefs.edit().putBoolean("real", real).apply()
    generation++
    connectJob?.cancel()
    disconnect()
    if (real && mockOn) {
      val kit = MockDeviceKit.getInstance(context)
      runCatching { kit.stopTestServer() }
      runCatching { kit.disable() }
      mockOn = false
      mockId = null
      _previewHint.value = null
    }
    scope.launch(errors) {
      delay(800) // let the old session close before opening a new one
      connectChosen()
    }
  }

  /** Version 1: Meta's simulated Ray-Ban Display glasses, lens viewable in Chrome. */
  fun connectMockGlasses() {
    if (session != null) return
    mockOn = true
    mockId?.let { id ->
      // reconnect: the simulated pair already exists, just open a new session to it
      startSession(SpecificDeviceSelector(id))
      return
    }
    val kit = MockDeviceKit.getInstance(context)
    kit.enable()
    kit.pairGlasses(GlassesModel.META_RAYBAN_DISPLAY)
        .fold(
            onSuccess = { glasses ->
              mockId = glasses.deviceIdentifier
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
              val gen = generation
              connectJob = scope.launch(errors) {
                _status.value = "Glasses: waiting for registration…"
                Wearables.registrationState.first { it == RegistrationState.REGISTERED }
                if (gen == generation) startSession(SpecificDeviceSelector(glasses.deviceIdentifier))
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
    val gen = generation
    connectJob = scope.launch(errors) {
      if (Wearables.registrationState.value != RegistrationState.REGISTERED) {
        _status.value = "Glasses: tap \"Connect to Meta AI\" and approve in the Meta AI app"
      }
      Wearables.registrationState.first { it == RegistrationState.REGISTERED }
      if (gen == generation) startSession(AutoDeviceSelector(filter = { it.isDisplayCapable() }))
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
    generation++ // our own stop: the STOPPED handler must not reconnect
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
    val gen = generation
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
                      if (gen == generation) {
                        // stopped by the glasses or the toolkit, not by us: connect again by ourselves
                        reconnects++
                        _status.value = "Glasses: session stopped, reconnecting ($reconnects)…"
                        Log.w(TAG, "Session stopped unexpectedly; reconnecting (#$reconnects)")
                        scope.launch(errors) {
                          delay(2_000)
                          if (session == null && gen == generation) connectChosen()
                        }
                      } else {
                        _status.value = "Glasses: session stopped"
                      }
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
                if (session == null && gen == generation) startSession(selector)
              }
            },
        )
  }

  private fun attachDisplay(s: DeviceSession) {
    _status.value = "Glasses: attaching display…"
    reconnects = 0
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

  private data class Frame(
      val display: Display?, val text: String, val size: TextSize, val signs: String?,
      val playing: Boolean, val alert: String? = null,
  )

  /** Demo: show a big warning (e.g. "FIRE ALARM") on the lens for [ms], then the captions return. */
  fun showAlert(label: String, ms: Long = 5_000) {
    alert.value = label
    scope.launch {
      delay(ms)
      if (alert.value == label) alert.value = null
    }
  }

  /** Show the sign names for a few seconds above the caption. */
  fun showSigns(signs: List<String>) {
    if (signs.isEmpty()) return
    val line = "Signs: " + signs.joinToString(" ") { it.removePrefix("FS:").let { s -> if (s != it) "($s)" else s } }
    signsLine.value = line
    scope.launch {
      delay(8_000)
      if (signsLine.value == line) signsLine.value = null
    }
  }

  private suspend fun draw(d: Display, text: String, size: TextSize, signs: String?, warning: String? = null) = sendLock.withLock {
    if (videoPlaying.value && warning == null) return@withLock // a video started while we waited
    val result =
        when {
          warning != null -> {
            val bitmap = TextBitmap.renderAlert(warning)
            d.sendContent {
              flexBox(direction = Direction.COLUMN) { image(bitmap = bitmap, sizePreset = ImageSize.FILL) }
            }
          }
          // Drawn as a picture: bigger than any built-in text style.
          size == TextSize.EXTRA_LARGE -> {
            val bitmap = TextBitmap.render(lastWords(text, 120).ifBlank { "Listening…" }, header = signs)
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
                if (signs != null) text(signs, style = TextStyle.META)
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
    scope.launch(Dispatchers.IO + errors) { playVideos(listOf(url)) }
  }

  /** Plays the clips one after another (the lens plays one video at a time), then back to captions. */
  suspend fun playVideos(urls: List<String>) {
    val d = display.value
    if (d == null) {
      _status.value = "Glasses: lens not ready for video"
      return
    }
    if (urls.isEmpty() || videoPlaying.value) return
    videoPlaying.value = true
    try {
      for ((i, url) in urls.withIndex()) {
        if (!playOne(d, url, "${i + 1}/${urls.size}")) break
      }
    } finally {
      videoPlaying.value = false // captions come back
    }
  }

  /** One clip, full screen. Returns false if it failed, so the rest of the sentence is skipped. */
  private suspend fun playOne(d: Display, url: String, label: String): Boolean {
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
      _status.value = "Glasses: playing video $label…"
      val started = System.currentTimeMillis()
      val result =
          withTimeoutOrNull(20_000) {
            combine(player.state, player.error) { state, error -> state to error }
                .first { (state, error) -> error != null || state == VideoPlayerState.ENDED }
          }
      val seconds = (System.currentTimeMillis() - started) / 1000.0
      Log.i(TAG, "Video $label done after ${seconds}s: $result ($url)")
      stateLog.cancel()
      errorLog.cancel()
      _status.value =
          when {
            result == null -> "Glasses: video $label timed out"
            result.second != null -> "Glasses: video $label error ${result.second}"
            else -> "Glasses: video $label played (${"%.1f".format(seconds)} s)"
          }
      return result != null && result.second == null
    } finally {
      player.close()
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
