package com.fyp.basarattradeinvest.feature.news.detail

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentNewsArticleDetailBinding
import com.fyp.basarattradeinvest.domain.model.news.NewsArticle
import kotlinx.coroutines.launch
import java.util.Locale

class NewsArticleDetailFragment : Fragment() {

    private var _binding: FragmentNewsArticleDetailBinding? = null
    private val binding get() = _binding!!

    private val viewModel: NewsArticleDetailViewModel by activityViewModels()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentNewsArticleDetailBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val articleId = arguments?.getString("articleId").orEmpty()

        setupListeners()
        observeUiState()

        if (articleId.isNotBlank()) {
            viewModel.ensureLoaded(articleId)
        } else {
            binding.tvErrorMessage.text = "Article ID not provided"
            binding.layoutErrorState.visibility = View.VISIBLE
            binding.scrollContent.visibility = View.GONE
        }
    }

    private fun setupListeners() {
        binding.ivBack.setOnClickListener {
            findNavController().popBackStack()
        }

        binding.btnRetry.setOnClickListener {
            viewModel.retry()
        }
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is NewsArticleDetailUiState.Loading -> {
                            binding.progressLoading.visibility = View.VISIBLE
                            binding.scrollContent.visibility = View.GONE
                            binding.layoutErrorState.visibility = View.GONE
                        }
                        is NewsArticleDetailUiState.Success -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.scrollContent.visibility = View.VISIBLE
                            binding.layoutErrorState.visibility = View.GONE
                            renderArticle(state.article)
                        }
                        is NewsArticleDetailUiState.Error -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.scrollContent.visibility = View.GONE
                            binding.layoutErrorState.visibility = View.VISIBLE
                            binding.tvErrorMessage.text = state.message
                        }
                    }
                }
            }
        }
    }

    private fun renderArticle(article: NewsArticle) {
        val context = requireContext()

        binding.tvArticleSource.text = article.source
        binding.tvOfficialBadge.visibility = if (article.isOfficial) View.VISIBLE else View.GONE
        binding.tvArticleTime.text = article.timestamp
        binding.tvArticleHeadline.text = article.headline
        binding.tvArticleBody.text = article.snippet

        // Generic news detail screens must not render sentiment badges.
        // Sentiment analysis is only relevant in dedicated stock/portfolio sentiment flows.
        binding.tvArticleSentiment.visibility = View.GONE
        binding.tvArticleSentiment.text = ""

        // Symbols chips
        binding.layoutSymbolsContainer.removeAllViews()
        val symbolsToShow = if (article.symbols.isNotEmpty()) article.symbols else listOf(article.symbol)
        symbolsToShow.distinct().forEach { sym ->
            val chip = TextView(context).apply {
                text = sym
                setTextAppearance(context, R.style.TextAppearance_Basarat_Body_Small_Strong)
                setBackgroundResource(R.drawable.bg_chip_filter_unselected)
                setPadding(24, 10, 24, 10)
                val params = ViewGroup.MarginLayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT
                ).apply {
                    setMargins(0, 0, 16, 0)
                }
                layoutParams = params
                isClickable = true
                isFocusable = true
                setOnClickListener {
                    val bundle = Bundle().apply { putString("symbol", sym) }
                    findNavController().navigate(R.id.stockDetailFragment, bundle)
                }
            }
            binding.layoutSymbolsContainer.addView(chip)
        }

        // External URL Action
        val targetUrl = article.url?.takeIf { it.isNotBlank() } ?: article.externalUrl?.takeIf { it.isNotBlank() }
        if (targetUrl != null) {
            binding.btnReadSource.visibility = View.VISIBLE
            binding.btnReadSource.setOnClickListener {
                findNavController().navigate(
                    R.id.newsWebViewFragment,
                    Bundle().apply { putString("url", targetUrl) }
                )
            }
        } else {
            binding.btnReadSource.visibility = View.GONE
        }

        // Share Action
        binding.ivShare.setOnClickListener {
            val shareText = "${article.headline}\n\nRead more via BASARAT: ${targetUrl.orEmpty()}"
            val sendIntent = Intent().apply {
                action = Intent.ACTION_SEND
                putExtra(Intent.EXTRA_TEXT, shareText)
                type = "text/plain"
            }
            val shareIntent = Intent.createChooser(sendIntent, null)
            startActivity(shareIntent)
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
