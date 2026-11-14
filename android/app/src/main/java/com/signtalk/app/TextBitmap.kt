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

  /** [header], if given, is drawn first in a smaller yellow line (used for the FinSL sign names). */
  fun render(text: String, textSizePx: Float = 36f, header: String? = null): Bitmap {
    val paint =
        TextPaint(TextPaint.ANTI_ALIAS_FLAG).apply {
          color = Color.WHITE
          textSize = textSizePx
          typeface = Typeface.DEFAULT_BOLD
        }
    val width = WIDTH - 2 * PADDING
    val headerLayout =
        header?.let {
          val hp = TextPaint(paint).apply { color = Color.YELLOW; textSize = textSizePx * 0.6f }
          layoutFor(it, hp, width)
        }
    val headerHeight = headerLayout?.height ?: 0
    // Keep only the lines that fit, newest at the bottom, like a caption.
    var layout = layoutFor(text, paint, width)
    val maxLines = ((HEIGHT - 2 * PADDING - headerHeight) / (paint.fontSpacing)).toInt().coerceAtLeast(1)
    if (layout.lineCount > maxLines) {
      val firstKept = layout.getLineStart(layout.lineCount - maxLines)
      layout = layoutFor(text.substring(firstKept).trimStart(), paint, width)
    }
    val bitmap = Bitmap.createBitmap(WIDTH, HEIGHT, Bitmap.Config.ARGB_8888)
    Canvas(bitmap).apply {
      drawColor(Color.BLACK)
      translate(PADDING.toFloat(), PADDING.toFloat())
      headerLayout?.let {
        it.draw(this)
        translate(0f, headerHeight.toFloat())
      }
      layout.draw(this)
    }
    return bitmap
  }

  /** The demo warning: a red frame, a warning sign and the sound's name in large letters. */
  fun renderAlert(label: String): Bitmap {
    val bitmap = Bitmap.createBitmap(WIDTH, HEIGHT, Bitmap.Config.ARGB_8888)
    val red = Color.rgb(255, 59, 48)
    Canvas(bitmap).apply {
      drawColor(Color.BLACK)
      val frame = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply {
        style = android.graphics.Paint.Style.STROKE; strokeWidth = 10f; color = red
      }
      drawRoundRect(6f, 6f, WIDTH - 6f, HEIGHT - 6f, 18f, 18f, frame)
      val icon = TextPaint(TextPaint.ANTI_ALIAS_FLAG).apply {
        color = red; textSize = 72f; typeface = Typeface.DEFAULT_BOLD; textAlign = android.graphics.Paint.Align.CENTER
      }
      drawText("⚠", WIDTH / 2f, 92f, icon)
      val words = TextPaint(TextPaint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE; typeface = Typeface.DEFAULT_BOLD; textAlign = android.graphics.Paint.Align.CENTER
        textSize = 40f
        while (measureText(label) > WIDTH - 40 && textSize > 20f) textSize -= 2f
      }
      drawText(label, WIDTH / 2f, 160f, words)
    }
    return bitmap
  }

  private fun layoutFor(text: String, paint: TextPaint, width: Int): StaticLayout =
      StaticLayout.Builder.obtain(text, 0, text.length, paint, width)
          .setAlignment(Layout.Alignment.ALIGN_NORMAL)
          .setLineSpacing(0f, 1.0f)
          .build()
}
