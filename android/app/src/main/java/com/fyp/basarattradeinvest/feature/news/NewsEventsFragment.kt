package com.fyp.basarattradeinvest.feature.news

import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentNewsEventsBinding
import com.fyp.basarattradeinvest.feature.news.adapter.NewsArticleAdapter
import kotlinx.coroutines.launch

class NewsEventsFragment : Fragment() {

    private var _binding: FragmentNewsEventsBinding? = null
    private val binding get() = _binding!!

    private val viewModel: NewsEventsViewModel by activityViewModels()

    private val newsAdapter by lazy {
        NewsArticleAdapter { article ->
            val bundle = Bundle().apply { putString("articleId", article.id) }
            findNavController().navigate(R.id.action_newsEvents_to_articleDetail, bundle)
        }
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentNewsEventsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupRecyclerView()
        setupListeners()
        observeUiState()
    }

    private fun setupRecyclerView() {
        val lm = LinearLayoutManager(requireContext())
        binding.rvNewsEvents.apply {
            layoutManager = lm
            adapter = newsAdapter
            addOnScrollListener(object : RecyclerView.OnScrollListener() {
                override fun onScrolled(recyclerView: RecyclerView, dx: Int, dy: Int) {
                    super.onScrolled(recyclerView, dx, dy)
                    if (dy > 0) {
                        val visibleItemCount = lm.childCount
                        val totalItemCount = lm.itemCount
                        val firstVisibleItemPosition = lm.findFirstVisibleItemPosition()

                        if ((visibleItemCount + firstVisibleItemPosition) >= totalItemCount - 3 && totalItemCount > 0) {
                            viewModel.loadNextPage()
                        }
                    }
                }
            })
        }
    }

    private fun setupListeners() {
        // Top Back
        binding.ivBack.setOnClickListener {
            findNavController().popBackStack()
        }

        // Refresh action
        binding.ivRefresh.setOnClickListener {
            viewModel.refreshNews()
        }

        // Help
        binding.ivHelp.setOnClickListener {
            Toast.makeText(
                requireContext(),
                "Real-time PSX intelligence, corporate announcements, and FinBERT sentiment scoring.",
                Toast.LENGTH_LONG
            ).show()
        }

        // Search Bar Toggle
        binding.ivSearch.setOnClickListener {
            if (binding.layoutSearchBar.visibility == View.VISIBLE) {
                binding.layoutSearchBar.visibility = View.GONE
                binding.etSearch.setText("")
            } else {
                binding.layoutSearchBar.visibility = View.VISIBLE
                binding.etSearch.requestFocus()
            }
        }

        binding.ivSearchClear.setOnClickListener {
            binding.etSearch.setText("")
        }

        binding.etSearch.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                viewModel.onSearchQueryChanged(s?.toString().orEmpty())
            }
            override fun afterTextChanged(s: Editable?) {}
        })

        // Filter Pills (Sectors & Corporate Categories)
        val filterMap = mapOf(
            binding.chipAll to "All",
            binding.chipGeneral to "General",
            binding.chipKse100 to "KSE-100",
            binding.chipBanks to "Banks",
            binding.chipCement to "Cement",
            binding.chipTech to "Technology",
            binding.chipOilGas to "Oil & Gas",
            binding.chipFertilizer to "Fertilizer",
            binding.chipCorporate to "Corporate",
            binding.chipEarnings to "Earnings",
            binding.chipDividends to "Dividends"
        )

        filterMap.forEach { (view, categoryName) ->
            view.setOnClickListener {
                viewModel.setCategory(categoryName)
            }
        }

        // Retry
        binding.btnRetry.setOnClickListener {
            viewModel.retry()
        }
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is NewsEventsUiState.Loading -> {
                            binding.progressLoading.visibility = View.VISIBLE
                            binding.rvNewsEvents.visibility = View.GONE
                            binding.layoutEmptyState.visibility = View.GONE
                            binding.layoutErrorState.visibility = View.GONE
                            binding.progressLoadMore.visibility = View.GONE
                        }
                        is NewsEventsUiState.Success -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.layoutErrorState.visibility = View.GONE

                            // Market Status Banner
                            if (!state.marketStatusText.isNullOrBlank()) {
                                binding.layoutMarketStatus.visibility = View.VISIBLE
                                binding.tvMarketStatus.text = state.marketStatusText
                            } else {
                                binding.layoutMarketStatus.visibility = View.GONE
                            }

                            // Load more progress indicator
                            binding.progressLoadMore.visibility = if (state.isLoadingMore) View.VISIBLE else View.GONE

                            // Refresh feedback toast if message present
                            if (!state.refreshMessage.isNullOrBlank() && !state.isRefreshing) {
                                Toast.makeText(requireContext(), state.refreshMessage, Toast.LENGTH_SHORT).show()
                            }

                            updateFilterPills(state.activeCategory)

                            if (state.newsArticles.isEmpty()) {
                                binding.rvNewsEvents.visibility = View.GONE
                                binding.layoutEmptyState.visibility = View.VISIBLE
                            } else {
                                binding.rvNewsEvents.visibility = View.VISIBLE
                                binding.layoutEmptyState.visibility = View.GONE
                                newsAdapter.submitList(state.newsArticles)
                            }
                        }
                        is NewsEventsUiState.Empty -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.rvNewsEvents.visibility = View.GONE
                            binding.layoutEmptyState.visibility = View.VISIBLE
                            binding.layoutErrorState.visibility = View.GONE
                            binding.progressLoadMore.visibility = View.GONE

                            updateFilterPills(state.activeCategory)
                        }
                        is NewsEventsUiState.Error -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.rvNewsEvents.visibility = View.GONE
                            binding.layoutEmptyState.visibility = View.GONE
                            binding.layoutErrorState.visibility = View.VISIBLE
                            binding.progressLoadMore.visibility = View.GONE
                            binding.tvErrorMessage.text = state.message
                        }
                    }
                }
            }
        }
    }

    private fun updateFilterPills(selectedCategory: String) {
        val pills = listOf(
            binding.chipAll to "All",
            binding.chipGeneral to "General",
            binding.chipKse100 to "KSE-100",
            binding.chipBanks to "Banks",
            binding.chipCement to "Cement",
            binding.chipTech to "Technology",
            binding.chipOilGas to "Oil & Gas",
            binding.chipFertilizer to "Fertilizer",
            binding.chipCorporate to "Corporate",
            binding.chipEarnings to "Earnings",
            binding.chipDividends to "Dividends"
        )

        pills.forEach { (view: TextView, categoryName: String) ->
            val isSelected = selectedCategory.equals(categoryName, ignoreCase = true)
            if (isSelected) {
                view.setBackgroundResource(R.drawable.bg_chip_filter_selected)
                view.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_positive))
            } else {
                view.setBackgroundResource(R.drawable.bg_chip_filter_unselected)
                view.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
