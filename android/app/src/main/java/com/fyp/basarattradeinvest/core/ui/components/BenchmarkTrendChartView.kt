package com.fyp.basarattradeinvest.core.ui.components

import android.content.Context
import android.graphics.Canvas
import android.graphics.DashPathEffect
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.Shader
import android.util.AttributeSet
import android.view.View
import androidx.core.content.ContextCompat
import com.fyp.basarattradeinvest.R
import kotlin.math.max
import kotlin.math.min

/** Compact, data-only single-series chart for the Home benchmark card. */
class BenchmarkTrendChartView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    private var values: List<Float> = emptyList()
    private var isPositive = true

    private val linePath = Path()
    private val areaPath = Path()
    private val gridPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.color_divider)
        alpha = 150
        strokeWidth = dp(1f)
        style = Paint.Style.STROKE
        pathEffect = DashPathEffect(floatArrayOf(dp(3f), dp(4f)), 0f)
    }
    private val baselinePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.color_text_tertiary)
        alpha = 90
        strokeWidth = dp(1f)
    }
    private val linePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = dp(2.5f)
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    private val areaPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
    private val endGlowPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
    private val endDotPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }

    fun setTrendData(points: List<Float>, positive: Boolean) {
        values = points.filter { it.isFinite() }
        isPositive = positive
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (width <= 0 || height <= 0 || values.size < 2) return

        val color = ContextCompat.getColor(
            context,
            if (isPositive) R.color.color_positive else R.color.color_negative
        )
        linePaint.color = color
        endDotPaint.color = ContextCompat.getColor(context, R.color.color_text_primary)

        val insetX = dp(5f)
        val insetY = dp(10f)
        val left = insetX
        val right = width - insetX
        val top = insetY
        val bottom = height - insetY
        val chartWidth = right - left
        val chartHeight = bottom - top
        if (chartWidth <= 0f || chartHeight <= 0f) return

        val low = min(0f, values.minOrNull() ?: 0f)
        val high = max(0f, values.maxOrNull() ?: 0f)
        val rawRange = (high - low).takeIf { it > 0f } ?: 0.1f
        val padding = rawRange * 0.12f
        val minValue = low - padding
        val maxValue = high + padding
        val range = maxValue - minValue
        fun yFor(value: Float): Float = bottom - ((value - minValue) / range) * chartHeight

        listOf(0.25f, 0.5f, 0.75f).forEach { fraction ->
            val y = top + chartHeight * fraction
            canvas.drawLine(left, y, right, y, gridPaint)
        }

        val zeroY = yFor(0f)
        canvas.drawLine(left, zeroY, right, zeroY, baselinePaint)

        val stepX = chartWidth / (values.size - 1)
        linePath.reset()
        areaPath.reset()
        val firstY = yFor(values.first())
        linePath.moveTo(left, firstY)
        areaPath.moveTo(left, zeroY)
        areaPath.lineTo(left, firstY)

        var endX = left
        var endY = firstY
        for (index in 1 until values.size) {
            val previousX = left + (index - 1) * stepX
            val previousY = yFor(values[index - 1])
            val currentX = left + index * stepX
            val currentY = yFor(values[index])
            val midpointX = (previousX + currentX) / 2f
            linePath.cubicTo(midpointX, previousY, midpointX, currentY, currentX, currentY)
            areaPath.cubicTo(midpointX, previousY, midpointX, currentY, currentX, currentY)
            endX = currentX
            endY = currentY
        }

        areaPath.lineTo(endX, zeroY)
        areaPath.close()
        areaPaint.shader = LinearGradient(
            0f,
            top,
            0f,
            bottom,
            (color and 0x00FFFFFF) or 0x26000000,
            (color and 0x00FFFFFF) or 0x00000000,
            Shader.TileMode.CLAMP
        )
        canvas.drawPath(areaPath, areaPaint)
        areaPaint.shader = null
        canvas.drawPath(linePath, linePaint)

        endGlowPaint.color = (color and 0x00FFFFFF) or 0x55000000
        canvas.drawCircle(endX, endY, dp(6f), endGlowPaint)
        canvas.drawCircle(endX, endY, dp(2.5f), linePaint)
        canvas.drawCircle(endX, endY, dp(1.2f), endDotPaint)
    }

    private fun dp(value: Float): Float = value * resources.displayMetrics.density
}
