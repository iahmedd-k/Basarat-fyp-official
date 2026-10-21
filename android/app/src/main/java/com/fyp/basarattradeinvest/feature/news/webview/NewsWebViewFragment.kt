package com.fyp.basarattradeinvest.feature.news.webview

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.net.http.SslError
import android.webkit.SslErrorHandler
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.fragment.app.Fragment
import androidx.navigation.fragment.findNavController
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentNewsWebViewBinding

class NewsWebViewFragment : Fragment() {

    private var _binding: FragmentNewsWebViewBinding? = null
    private val binding get() = _binding!!

    private var currentUrl: String? = null
    private var pageLoaded = false
    private var handedOffToBrowser = false

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentNewsWebViewBinding.inflate(inflater, container, false)
        return binding.root
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val url = arguments?.getString("url")?.takeIf { it.isNotBlank() }
        val uri = url?.let { runCatching { Uri.parse(it) }.getOrNull() }
            ?.takeIf { (it.scheme == "http" || it.scheme == "https") && !it.host.isNullOrBlank() }

        binding.ivBack.setOnClickListener { findNavController().popBackStack() }
        binding.ivOpenExternal.setOnClickListener {
            openExternally(currentUrl ?: url, explicit = true)
        }

        if (uri == null) {
            binding.tvHost.text = ""
            showError()
            return
        }

        currentUrl = url
        binding.tvHost.text = uri.host?.removePrefix("www.")

        binding.webView.apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = true
            settings.loadWithOverviewMode = true
            settings.useWideViewPort = true

            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(
                    view: WebView,
                    request: WebResourceRequest
                ): Boolean {
                    val scheme = request.url.scheme?.lowercase()
                    return scheme != "http" && scheme != "https"
                }

                override fun onPageFinished(view: WebView, finishedUrl: String) {
                    if (_binding == null) return
                    currentUrl = finishedUrl
                    pageLoaded = true
                    binding.progressBar.visibility = View.GONE
                }

                override fun onReceivedError(
                    view: WebView,
                    request: WebResourceRequest,
                    error: WebResourceError
                ) {
                    if (request.isForMainFrame) showError()
                }

                // The device's system trust store decides what WebView accepts, and on older
                // Android it lacks the newer CA roots Chrome ships with — so a source can verify
                // fine in the browser and fail here. Hand those reads to the browser instead of
                // leaving a blank screen; proceeding anyway would disable certificate validation.
                // Only before the article has painted, since an ad or tracker with a bad
                // certificate must not throw a working page out of the app.
                override fun onReceivedSslError(
                    view: WebView,
                    handler: SslErrorHandler,
                    error: SslError
                ) {
                    handler.cancel()
                    if (!pageLoaded) openExternally(view.url ?: currentUrl)
                }
            }

            webChromeClient = object : WebChromeClient() {
                override fun onProgressChanged(view: WebView, newProgress: Int) {
                    val bar = _binding?.progressBar ?: return
                    if (newProgress < 100) {
                        bar.visibility = View.VISIBLE
                        bar.progress = newProgress
                    } else {
                        bar.visibility = View.GONE
                    }
                }
            }

            loadUrl(uri.toString())
        }

        requireActivity().onBackPressedDispatcher.addCallback(
            viewLifecycleOwner,
            object : OnBackPressedCallback(true) {
                override fun handleOnBackPressed() {
                    val webView = _binding?.webView
                    if (webView != null && webView.canGoBack()) {
                        webView.goBack()
                    } else {
                        isEnabled = false
                        findNavController().popBackStack()
                    }
                }
            }
        )
    }

    private fun openExternally(target: String?, explicit: Boolean = false) {
        val b = _binding ?: return
        if (target.isNullOrBlank()) {
            showError()
            return
        }
        if (!explicit) {
            if (handedOffToBrowser) return
            handedOffToBrowser = true
            b.webView.stopLoading()
        }

        val opened = runCatching {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(target)))
        }.isSuccess

        if (!opened) {
            showError()
            return
        }
        if (!explicit) {
            Toast.makeText(requireContext(), R.string.news_webview_opened_externally, Toast.LENGTH_LONG).show()
            findNavController().popBackStack()
        }
    }

    private fun showError() {
        val b = _binding ?: return
        b.progressBar.visibility = View.GONE
        b.webView.visibility = View.GONE
        b.tvError.visibility = View.VISIBLE
    }

    override fun onDestroyView() {
        _binding?.webView?.let { webView ->
            webView.stopLoading()
            (webView.parent as? ViewGroup)?.removeView(webView)
            webView.destroy()
        }
        _binding = null
        super.onDestroyView()
    }
}
