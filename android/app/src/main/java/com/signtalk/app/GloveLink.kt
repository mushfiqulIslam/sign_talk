package com.signtalk.app

import android.content.Context
import android.net.wifi.WifiManager
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetSocketAddress
import java.net.SocketTimeoutException
import java.net.Socket
import java.util.Locale
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject

private const val TAG = "SignTalkGloves"
private const val PORT = 8765
private const val DISCOVERY_PORT = 8767

/** A laptop running the glove backend, heard announcing itself on the Wi-Fi. */
data class FoundLaptop(val name: String, val host: String, val port: Int)

/** One signed sentence from the gloves, in both languages. */
data class GloveSentence(val signs: List<String>, val fi: String, val en: String, val by: String)

/**
 * Talks to the glove backend (`signtalk-gloves run`) on a laptop on the same Wi-Fi:
 * receives each recognised sign and sentence, and speaks the sentence out loud for the hearing person.
 */
class GloveLink(context: Context, private val scope: CoroutineScope) {

  private val prefs = context.getSharedPreferences("gloves", Context.MODE_PRIVATE)

  private val _host = MutableStateFlow(prefs.getString("host", null) ?: BuildConfig.GLOVE_HOST)
  val host: StateFlow<String> = _host.asStateFlow()

  private val _status = MutableStateFlow("Not connected")
  val status: StateFlow<String> = _status.asStateFlow()

  private val _connected = MutableStateFlow(false)
  val connected: StateFlow<Boolean> = _connected.asStateFlow()

  /** Signs of the sentence being signed right now. */
  private val _liveSigns = MutableStateFlow<List<String>>(emptyList())
  val liveSigns: StateFlow<List<String>> = _liveSigns.asStateFlow()

  private val _sentence = MutableStateFlow<GloveSentence?>(null)
  val sentence: StateFlow<GloveSentence?> = _sentence.asStateFlow()

  /** Which language to speak; set by the screen's language switch. */
  var finnish: () -> Boolean = { true }
  /** Called around speaking, so the caption mic can pause and not caption our own voice. */
  var onSpeaking: (Boolean) -> Unit = {}

  private val _found = MutableStateFlow<List<FoundLaptop>>(emptyList())
  /** Laptops heard on the Wi-Fi in the last few seconds. */
  val found: StateFlow<List<FoundLaptop>> = _found.asStateFlow()
  private val lastHeard = mutableMapOf<String, Pair<FoundLaptop, Long>>()
  /** After the user taps Disconnect, don't connect again by ourselves. */
  private var userDisconnected = false
  private var port = PORT

  private val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
  private var discoveryJob: Job? = null

  private var job: Job? = null
  @Volatile private var socket: Socket? = null
  private var sentenceDone = true

  private var ttsReady = false
  private val tts =
      TextToSpeech(context) { ok -> ttsReady = ok == TextToSpeech.SUCCESS }.apply {
        setOnUtteranceProgressListener(
            object : UtteranceProgressListener() {
              override fun onStart(id: String?) = scope.launch(Dispatchers.Main) { onSpeaking(true) }.let {}
              override fun onDone(id: String?) = scope.launch(Dispatchers.Main) { onSpeaking(false) }.let {}
              @Deprecated("old API") override fun onError(id: String?) = scope.launch(Dispatchers.Main) { onSpeaking(false) }.let {}
            })
      }

  fun setHost(value: String) {
    _host.value = value.trim()
  }

  /** Listens for laptops announcing "Sign Talk gloves here" (UDP broadcast, port 8767). */
  fun startDiscovery() {
    if (discoveryJob != null) return
    discoveryJob =
        scope.launch(Dispatchers.IO) {
          // some phones drop broadcast packets unless an app holds this lock
          val lock = wifi.createMulticastLock("signtalk-gloves").apply { setReferenceCounted(false) }
          runCatching { lock.acquire() }
          try {
            DatagramSocket(null).use { sock ->
              sock.reuseAddress = true
              sock.broadcast = true
              sock.soTimeout = 1_000
              sock.bind(InetSocketAddress(DISCOVERY_PORT))
              val buf = ByteArray(2048)
              while (isActive) {
                val packet = DatagramPacket(buf, buf.size)
                try {
                  sock.receive(packet)
                  val m = JSONObject(String(packet.data, 0, packet.length, Charsets.UTF_8))
                  if (m.optString("type") == "signtalk-gloves") {
                    val laptop =
                        FoundLaptop(m.optString("name", "Laptop"), packet.address.hostAddress ?: continue, m.optInt("port", PORT))
                    synchronized(lastHeard) { lastHeard[laptop.host] = laptop to System.currentTimeMillis() }
                  }
                } catch (_: SocketTimeoutException) {
                } catch (_: org.json.JSONException) {
                }
                refreshFound()
              }
            }
          } catch (e: Exception) {
            Log.w(TAG, "discovery stopped: ${e.javaClass.simpleName}: ${e.message}")
          } finally {
            runCatching { lock.release() }
          }
        }
  }

  private fun refreshFound() {
    val now = System.currentTimeMillis()
    val list =
        synchronized(lastHeard) {
          lastHeard.entries.removeAll { now - it.value.second > 5_000 }
          lastHeard.values.map { it.first }.sortedBy { it.name }
        }
    if (list != _found.value) _found.value = list
    // exactly one laptop on the Wi-Fi and we're not connected: pair with it by ourselves
    if (job == null && !userDisconnected && list.size == 1) {
      scope.launch(Dispatchers.Main) { if (job == null) connectTo(list[0]) }
    }
  }

  /** The laptop's QR code (`signtalk://connect?host=..&port=..&name=..`). False if it isn't one of ours. */
  fun connectFromLink(link: String): Boolean {
    val uri = runCatching { android.net.Uri.parse(link) }.getOrNull() ?: return false
    if (uri.scheme != "signtalk" || uri.host != "connect") return false
    val host = uri.getQueryParameter("host")?.takeIf { it.isNotBlank() } ?: return false
    val port = uri.getQueryParameter("port")?.toIntOrNull() ?: PORT
    connectTo(FoundLaptop(uri.getQueryParameter("name") ?: "Laptop", host, port))
    return true
  }

  /** Tap on a found laptop. */
  fun connectTo(laptop: FoundLaptop) {
    _host.value = laptop.host
    port = laptop.port
    connect()
  }

  fun connect() {
    userDisconnected = false
    val target = _host.value
    if (target.isBlank()) {
      _status.value = "Type the laptop's address first"
      return
    }
    prefs.edit().putString("host", target).apply()
    disconnect()
    job =
        scope.launch(Dispatchers.IO) {
          while (isActive) {
            _status.value = "Connecting to $target…"
            try {
              Socket().use { s ->
                s.connect(InetSocketAddress(target, port), 5_000)
                s.tcpNoDelay = true
                socket = s
                _connected.value = true
                _status.value = "Connected to $target"
                Log.i(TAG, "connected to $target:$port")
                val reader = BufferedReader(InputStreamReader(s.getInputStream(), Charsets.UTF_8))
                while (isActive) {
                  val line = reader.readLine() ?: break
                  handle(line)
                }
              }
            } catch (e: Exception) {
              Log.w(TAG, "glove link: ${e.javaClass.simpleName}: ${e.message}")
            }
            socket = null
            _connected.value = false
            if (!isActive) break
            _status.value = "Lost $target, retrying…"
            delay(3_000)
          }
        }
  }

  /** The Disconnect button: also stops pairing by ourselves until Connect is tapped. */
  fun disconnectByUser() {
    userDisconnected = true
    disconnect()
  }

  fun disconnect() {
    job?.cancel()
    job = null
    runCatching { socket?.close() }
    socket = null
    _connected.value = false
    _status.value = "Not connected"
  }

  /** Ask the laptop to replay the next recorded demo phrase. */
  fun requestReplay() {
    val s = socket ?: return
    scope.launch(Dispatchers.IO) {
      runCatching { s.getOutputStream().apply { write("{\"type\": \"replay\"}\n".toByteArray()); flush() } }
    }
  }

  fun speakAgain() {
    _sentence.value?.let { speak(it) }
  }

  private fun handle(line: String) {
    val m = runCatching { JSONObject(line) }.getOrNull() ?: return
    when (m.optString("type")) {
      "status" -> _status.value = m.optString("text")
      "sign" -> {
        if (sentenceDone) {
          _liveSigns.value = emptyList()
          sentenceDone = false
        }
        _liveSigns.value = _liveSigns.value + m.optString("sign")
      }
      "sentence" -> {
        val signs = m.optJSONArray("signs")
        val s =
            GloveSentence(
                signs = List(signs?.length() ?: 0) { signs!!.getString(it) },
                fi = m.optString("fi"),
                en = m.optString("en"),
                by = m.optString("by"),
            )
        sentenceDone = true
        _liveSigns.value = s.signs
        _sentence.value = s
        speak(s)
      }
    }
  }

  private fun speak(s: GloveSentence) {
    if (!ttsReady) return
    val fi = finnish()
    tts.language = if (fi) Locale.forLanguageTag("fi-FI") else Locale.US
    tts.speak(if (fi) s.fi else s.en, TextToSpeech.QUEUE_FLUSH, null, "glove-${System.nanoTime()}")
  }

  fun close() {
    discoveryJob?.cancel()
    disconnect()
    tts.shutdown()
  }
}
