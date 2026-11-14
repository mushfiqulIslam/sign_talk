package com.signtalk.app

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Typeface
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint

/**
 * Draws caption text as a picture, so the lens can show it bigger than its largest
 * text style (HEADING). Black is see-through on the glasses, so it is white on black.
 */
object TextBitmap {
  private const val WIDTH = 300
  private const val HEIGHT = 200
  private const val PADDING = 12

  fun render(text: String, textSizePx: Float = 36f): Bitmap {
    val paint =
        TextPaint(TextPaint.ANTI_ALIAS_FLAG).apply {
          color = Color.WHITE
          textSize = textSizePx
          typeface = Typeface.DEFAULT_BOLD
        }
    val width = WIDTH - 2 * PADDING
    // Keep only the lines that fit, newest at the bottom, like a caption.
    var layout = layoutFor(text, paint, width)
    val maxLines = ((HEIGHT - 2 * PADDING) / (paint.fontSpacing)).toInt().coerceAtLeast(1)
    if (layout.lineCount > maxLines) {
      val firstKept = layout.getLineStart(layout.lineCount - maxLines)
      layout = layoutFor(text.substring(firstKept).trimStart(), paint, width)
    }
    val bitmap = Bitmap.createBitmap(WIDTH, HEIGHT, Bitmap.Config.ARGB_8888)
    Canvas(bitmap).apply {
      drawColor(Color.BLACK)
      translate(PADDING.toFloat(), PADDING.toFloat())
      layout.draw(this)
    }
    return bitmap
  }

  private fun layoutFor(text: String, paint: TextPaint, width: Int): StaticLayout =
      StaticLayout.Builder.obtain(text, 0, text.length, paint, width)
          .setAlignment(Layout.Alignment.ALIGN_NORMAL)
          .setLineSpacing(0f, 1.0f)
          .build()
}
