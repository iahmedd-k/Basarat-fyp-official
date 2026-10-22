package com.fyp.basarattradeinvest.core.ui.components

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.DashPathEffect
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.Shader
import android.util.AttributeSet
import android.view.View

class IntradayChartView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    companion object {
        // Realistic default intraday curve for KSE-100 (9:30 AM to 3:30 PM)
        private val DEFAULT_PRIMARY_POINTS = listOf(
            85620f, 85580f, 85510f, 85460f, 85390f, 85340f, 85290f, 85240f,
            85270f, 85310f, 85280f, 85220f, 85180f, 85240f, 85300f, 85360f,
            85390f, 85410f, 85435f, 85421f
        )

        // Realistic default intraday curve for KMI-30 (Islamic Index)
        private val DEFAULT_SECONDARY_POINTS = listOf(
            143710f, 143680f, 143630f, 143590f, 143540f, 143500f, 143470f, 143490f,
            143520f, 143480f, 143450f, 143430f, 143460f, 143500f, 143530f, 143550f,
            143565f, 143580f, 143570f, 143579f
        )
    }

    private var primaryPoints: List<Float> = DEFAULT_PRIMARY_POINTS
    private var secondaryPoints: List<Float> = DEFAULT_SECONDARY_POINTS

    private val primaryColor = Color.parseColor("#00E5FF") // Vibrant Cyan (Line 1: KSE-100)
    private val secondaryColor = Color.parseColor("#9D4EDD") // Vibrant Purple (Line 2: KMI-30)

    private val primaryPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = primaryColor
        strokeWidth = 3.5f
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }

    private val secondaryPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = secondaryColor
        strokeWidth = 3.5f
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }

    private val primaryFillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
    }

    private val secondaryFillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
    }

    private val gridPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#1FFFFFFF")
        strokeWidth = 1.5f
        style = Paint.Style.STROKE
        pathEffect = DashPathEffect(floatArrayOf(6f, 6f), 0f)
    }

    private val dotGlowPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
    }

    private val dotSolidPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
        color = Color.WHITE
    }

    private val primaryPath = Path()
    private val secondaryPath = Path()
    private val primaryFillPath = Path()
    private val secondaryFillPath = Path()
    private val gridPath = Path()

    fun setChartData(primary: List<Float>, secondary: List<Float>) {
        if (primary.isNotEmpty()) this.primaryPoints = primary
        if (secondary.isNotEmpty()) this.secondaryPoints = secondary
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (width <= 0 || height <= 0) return

        val paddingVertical = 16f
        val paddingRight = 10f
        val chartHeight = height.toFloat() - (paddingVertical * 2)
        val chartWidth = width.toFloat() - paddingRight

        // Draw horizontal dashed grid lines at 25%, 50%, and 75% of height
        drawGridLines(canvas, chartWidth)

        // Draw secondary series (KMI-30: Purple)
        if (secondaryPoints.size >= 2) {
            drawSeriesWithFill(
                canvas = canvas,
                points = secondaryPoints,
                path = secondaryPath,
                fillPath = secondaryFillPath,
                strokePaint = secondaryPaint,
                fillPaint = secondaryFillPaint,
                color = secondaryColor,
                w = chartWidth,
                h = chartHeight,
                topPadding = paddingVertical
            )
        }

        // Draw primary series (KSE-100: Cyan)
        if (primaryPoints.size >= 2) {
            drawSeriesWithFill(
                canvas = canvas,
                points = primaryPoints,
                path = primaryPath,
                fillPath = primaryFillPath,
                strokePaint = primaryPaint,
                fillPaint = primaryFillPaint,
                color = primaryColor,
                w = chartWidth,
                h = chartHeight,
                topPadding = paddingVertical
            )
        }
    }

    private fun drawGridLines(canvas: Canvas, w: Float) {
        val step = height / 4f
        for (i in 1..3) {
            val y = step * i
            gridPath.reset()
            gridPath.moveTo(0f, y)
            gridPath.lineTo(w, y)
            canvas.drawPath(gridPath, gridPaint)
        }
    }

    private fun drawSeriesWithFill(
        canvas: Canvas,
        points: List<Float>,
        path: Path,
        fillPath: Path,
        strokePaint: Paint,
        fillPaint: Paint,
        color: Int,
        w: Float,
        h: Float,
        topPadding: Float
    ) {
        path.reset()
        fillPath.reset()

        val minVal = points.minOrNull() ?: 0f
        val maxVal = points.maxOrNull() ?: 1f
        val range = if (maxVal - minVal == 0f) 1f else maxVal - minVal

        val stepX = w / (points.size - 1)

        val firstY = topPadding + (h - ((points[0] - minVal) / range) * h)
        path.moveTo(0f, firstY)
        fillPath.moveTo(0f, topPadding + h)
        fillPath.lineTo(0f, firstY)

        var lastX = 0f
        var lastY = firstY

        for (i in 1 until points.size) {
            val prevX = (i - 1) * stepX
            val prevY = topPadding + (h - ((points[i - 1] - minVal) / range) * h)
            val currentX = i * stepX
            val currentY = topPadding + (h - ((points[i] - minVal) / range) * h)

            val midX = (prevX + currentX) / 2
            path.cubicTo(midX, prevY, midX, currentY, currentX, currentY)
            fillPath.cubicTo(midX, prevY, midX, currentY, currentX, currentY)

            lastX = currentX
            lastY = currentY
        }

        // Complete fill path down to baseline
        fillPath.lineTo(lastX, topPadding + h)
        fillPath.close()

        // Area gradient fill
        fillPaint.shader = LinearGradient(
            0f, topPadding,
            0f, topPadding + h,
            adjustAlpha(color, 0.18f),
            Color.TRANSPARENT,
            Shader.TileMode.CLAMP
        )
        canvas.drawPath(fillPath, fillPaint)

        // Draw line curve
        canvas.drawPath(path, strokePaint)

        // Glowing end point dot
        dotGlowPaint.color = adjustAlpha(color, 0.40f)
        canvas.drawCircle(lastX, lastY, 7f, dotGlowPaint)

        dotGlowPaint.color = color
        canvas.drawCircle(lastX, lastY, 4f, dotGlowPaint)

        canvas.drawCircle(lastX, lastY, 2f, dotSolidPaint)
    }

    private fun adjustAlpha(color: Int, factor: Float): Int {
        val alpha = Math.round(Color.alpha(color) * factor)
        val red = Color.red(color)
        val green = Color.green(color)
        val blue = Color.blue(color)
        return Color.argb(alpha, red, green, blue)
    }
}
