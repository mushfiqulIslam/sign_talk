package com.signtalk.app

/**
 * Turns a stream of partial and final speech results into the caption text we show:
 * the last few finished sentences plus whatever is being said right now.
 * Used for both the phone microphone and the glasses microphone.
 */
class Transcript(private val keepSentences: Int = 3) {
  private val finished = ArrayDeque<String>()
  private var current = ""

  /** Words still being spoken; replaced by the next partial for the same sentence. */
  fun partial(text: String): String {
    current = text
    return text()
  }

  /** A finished sentence; kept, and the "being spoken" part is cleared. */
  fun final(text: String): String {
    if (text.isNotBlank()) {
      finished.addLast(text)
      while (finished.size > keepSentences) finished.removeFirst()
    }
    current = ""
    return text()
  }

  fun clear(): String {
    finished.clear()
    current = ""
    return ""
  }

  fun text(): String = (finished + current).filter { it.isNotBlank() }.joinToString(" ")
}
