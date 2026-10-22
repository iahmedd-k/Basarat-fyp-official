package com.fyp.basarattradeinvest.core.ui.components

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.Shader
import android.util.AttributeSet
import android.view.View

/**
 * Lightweight, high-performance sparkline chart for high-density cards (e.g. Watchlist).
 */
class MiniSparklineView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    private var points: List<Float> = emptyList()
    private var isPositive: Boolean = true

    private val linePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        strokeWidth = 3f
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }

    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
    }

    private val linePath = Path()
    private val fillPath = Path()

    fun setTrend(isPositive: Boolean, customPoints: List<Float>? = null) {
        this.isPositive = isPositive
        this.points = customPoints ?: if (isPositive) {
            listOf(10f, 12f, 11f, 15f, 14f, 18f, 17f, 22f, 20f, 25f)
        } else {
            listOf(25f, 22f, 23f, 18f, 19f, 15f, 16f, 12f, 13f, 10f)
        }
        val strokeColor = if (isPositive) Color.parseColor("#18B981") else Color.parseColor("#EF4444")
        linePaint.color = strokeColor
        invalidate()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        updateGradient(w, h)
    }

    private fun updateGradient(w: Int, h: Int) {
        if (w <= 0 || h <= 0) return
        val fillColor = if (isPositive) Color.parseColor("#18B981") else Color.parseColor("#EF4444")
        val alphaTop = Color.argb(45, Color.red(fillColor), Color.green(fillColor), Color.blue(fillColor))
        val alphaBottom = Color.TRANSPARENT
        fillPaint.shader = LinearGradient(
            0f, 0f, 0f, h.toFloat(),
            alphaTop, alphaBottom,
            Shader.TileMode.CLAMP
        )
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (points.size < 2 || width <= 0 || height <= 0) return

        linePath.reset()
        fillPath.reset()

        val minVal = points.minOrNull() ?: 0f
        val maxVal = points.maxOrNull() ?: 1f
        val range = if (maxVal - minVal == 0f) 1f else (maxVal - minVal)

        val paddingH = 4f
        val paddingV = 4f
        val usableW = width - (paddingH * 2)
        val usableH = height - (paddingV * 2)
        val stepX = usableW / (points.size - 1)

        val coords = points.mapIndexed { index, value ->
            val x = paddingH + (index * stepX)
            val normalizedY = (value - minVal) / range
            val y = paddingV + usableH - (normalizedY * usableH)
            Pair(x, y)
        }

        linePath.moveTo(coords[0].first, coords[0].second)
        fillPath.moveTo(coords[0].first, height.toFloat())
        fillPath.lineTo(coords[0].first, coords[0].second)

        for (i in 0 until coords.size - 1) {
            val p0 = coords[i]
            val p1 = coords[i + 1]
            val midX = (p0.first + p1.first) / 2f
            linePath.cubicTo(midX, p0.second, midX, p1.second, p1.first, p1.second)
            fillPath.cubicTo(midX, p0.second, midX, p1.second, p1.first, p1.second)
        }

        fillPath.lineTo(coords.last().first, height.toFloat())
        fillPath.close()

        canvas.drawPath(fillPath, fillPaint)
        canvas.drawPath(linePath, linePaint)
    }
}
