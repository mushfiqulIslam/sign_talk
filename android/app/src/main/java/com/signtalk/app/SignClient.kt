package com.signtalk.app

import android.util.Log
import java.net.HttpURLConnection
import java.net.URL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

private const val TAG = "SignTalkSigns"

/** What the sign API sends back for one sentence. [videos] has a link per sign, or null (fingerspelled). */
data class SignResult(
    val signs: List<String>, val videos: List<String?>, val dropped: List<String>, val ms: Int,
    /** One joined, lens-sized video for the whole sentence (full https address), if the server made one. */
    val sentenceVideo: String? = null,
)

/**
 * Asks our fine-tuned Gemma (on the Verda GPU) for the FinSL signs of one finished sentence.
 * Returns null on any problem, so captions just carry on without signs.
 */
class SignClient(private val baseUrl: String, private val key: String) {

  val configured: Boolean
    get() = baseUrl.isNotBlank() && key.isNotBlank()

  suspend fun signs(text: String, language: Language): SignResult? =
      withContext(Dispatchers.IO) {
        if (!configured) return@withContext null
        val lang = if (language == Language.FINNISH) "fi" else "en"
        try {
          val conn = (URL("$baseUrl/signs").openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 3_000
            readTimeout = 15_000 // first time a sentence's video is built takes a few seconds
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("x-api-key", key)
          }
          conn.outputStream.use { it.write(JSONObject().put("text", text).put("lang", lang).toString().toByteArray()) }
          if (conn.responseCode != 200) {
            Log.w(TAG, "Sign API answered ${conn.responseCode}")
            return@withContext null
          }
          val body = JSONObject(conn.inputStream.bufferedReader().readText())
          val signs = body.getJSONArray("signs")
          val videos = body.getJSONArray("videos")
          val dropped = body.getJSONArray("dropped")
          SignResult(
              signs = List(signs.length()) { signs.getString(it) },
              videos = List(videos.length()) { if (videos.isNull(it)) null else videos.getString(it) },
              dropped = List(dropped.length()) { dropped.getString(it) },
              ms = body.optInt("ms"),
              sentenceVideo =
                  body.optString("video").takeIf { it.startsWith("/v/") && baseUrl.startsWith("https://") }
                      ?.let { baseUrl.trimEnd('/') + it },
          )
        } catch (e: Exception) {
          Log.w(TAG, "Sign API failed: ${e.javaClass.simpleName}: ${e.message}")
          null
        }
      }
}
