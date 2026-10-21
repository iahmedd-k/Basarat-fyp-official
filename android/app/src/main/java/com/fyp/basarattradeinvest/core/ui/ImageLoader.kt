package com.fyp.basarattradeinvest.core.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.LruCache
import android.view.View
import android.widget.ImageView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.ConcurrentHashMap

object ImageLoader {

    private val maxMemory = (Runtime.getRuntime().maxMemory() / 1024).toInt()
    private val cacheSize = maxMemory / 8

    private val memoryCache = object : LruCache<String, Bitmap>(cacheSize) {
        override fun sizeOf(key: String, bitmap: Bitmap): Int {
            return bitmap.byteCount / 1024
        }
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    // A fling rebinds the same still-loading URL many times; without this each bind started its
    // own download and full-size decode, which is what spiked RSS far enough for MIUI to reap us.
    private val inFlight = ConcurrentHashMap<String, Deferred<Bitmap?>>()

    fun loadImage(imageView: ImageView, url: String?) {
        if (url.isNullOrBlank()) {
            imageView.visibility = View.GONE
            return
        }

        val cachedBitmap = memoryCache.get(url)
        if (cachedBitmap != null) {
            imageView.setImageBitmap(cachedBitmap)
            imageView.visibility = View.VISIBLE
            return
        }

        imageView.tag = url
        val request = inFlight.getOrPut(url) {
            scope.async {
                try {
                    withContext(Dispatchers.IO) {
                        downloadBitmap(url, imageView.width, imageView.height)
                    }
                } finally {
                    inFlight.remove(url)
                }
            }
        }

        scope.launch {
            val bitmap = request.await()
            if (bitmap != null) {
                memoryCache.put(url, bitmap)
                if (imageView.tag == url) {
                    imageView.setImageBitmap(bitmap)
                    imageView.visibility = View.VISIBLE
                }
            } else {
                if (imageView.tag == url) {
                    imageView.visibility = View.GONE
                }
            }
        }
    }

    private fun downloadBitmap(urlStr: String, targetWidth: Int, targetHeight: Int): Bitmap? {
        return try {
            val url = URL(urlStr)
            val connection = url.openConnection() as HttpURLConnection
            connection.doInput = true
            connection.connectTimeout = 10000
            connection.readTimeout = 10000
            connection.connect()
            val bytes = connection.inputStream.use { it.readBytes() }

            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
            if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null

            val options = BitmapFactory.Options().apply {
                inSampleSize = sampleSize(
                    bounds.outWidth,
                    bounds.outHeight,
                    if (targetWidth > 0) targetWidth else MAX_DECODE_WIDTH,
                    if (targetHeight > 0) targetHeight else MAX_DECODE_WIDTH
                )
            }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
        } catch (_: Exception) {
            null
        }
    }

    private fun sampleSize(width: Int, height: Int, targetWidth: Int, targetHeight: Int): Int {
        var sample = 1
        val longestTarget = maxOf(targetWidth, targetHeight).coerceAtMost(MAX_DECODE_WIDTH)
        var longestSide = maxOf(width, height)
        while (longestSide / sample > longestTarget) {
            sample *= 2
        }
        return sample
    }

    private const val MAX_DECODE_WIDTH = 1080
}
