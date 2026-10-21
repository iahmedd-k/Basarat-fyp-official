package com.fyp.basarattradeinvest.feature.watchlist

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.GridLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentWatchlistBinding
import kotlinx.coroutines.launch

class WatchlistFragment : Fragment() {

    private var _binding: FragmentWatchlistBinding? = null
    private val binding get() = _binding!!

    private val viewModel: WatchlistViewModel by activityViewModels()
    private lateinit var adapter: WatchlistAdapter

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentWatchlistBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        adapter = WatchlistAdapter(
            onStockClick = { item ->
                val bundle = Bundle().apply { putString("symbol", item.symbol) }
                findNavController().navigate(R.id.stockDetailFragment, bundle)
            },
            onRemoveClick = { item -> viewModel.remove(item.symbol, item.watchlistId) }
        )

        binding.rvWatchlist.layoutManager = GridLayoutManager(requireContext(), 2)
        binding.rvWatchlist.adapter = adapter

        binding.ivBack.setOnClickListener { findNavController().popBackStack() }
        binding.btnAddStocks.setOnClickListener { openStockSearch() }
        binding.btnEmptyAdd.setOnClickListener { openStockSearch() }
        binding.btnRetry.setOnClickListener { viewModel.load() }
        binding.swipeRefresh.setOnRefreshListener { viewModel.load() }

        observeUiState()
        observeMessages()
    }

    private fun openStockSearch() {
        findNavController().navigate(R.id.stockSearchFragment)
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is WatchlistScreenUiState.Loading -> {
                            binding.swipeRefresh.isRefreshing = false
                            binding.layoutLoading.visibility = View.VISIBLE
                            binding.layoutEmpty.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                            binding.rvWatchlist.visibility = View.GONE
                            binding.btnAddStocks.visibility = View.GONE
                            binding.tvWatchlistCount.text = "Loading…"
                        }
                        is WatchlistScreenUiState.Error -> {
                            binding.swipeRefresh.isRefreshing = false
                            binding.layoutLoading.visibility = View.GONE
                            binding.layoutEmpty.visibility = View.GONE
                            binding.layoutError.visibility = View.VISIBLE
                            binding.rvWatchlist.visibility = View.GONE
                            binding.btnAddStocks.visibility = View.GONE
                            binding.tvErrorMessage.text = state.message
                            binding.tvWatchlistCount.text = "Not available"
                        }
                        is WatchlistScreenUiState.Loaded -> {
                            binding.swipeRefresh.isRefreshing = false
                            binding.layoutLoading.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                            val isEmpty = state.items.isEmpty()
                            binding.layoutEmpty.visibility = if (isEmpty) View.VISIBLE else View.GONE
                            binding.rvWatchlist.visibility = if (isEmpty) View.GONE else View.VISIBLE
                            binding.btnAddStocks.visibility = if (isEmpty) View.GONE else View.VISIBLE
                            adapter.submitList(state.items, state.pendingRemovals)
                            binding.tvWatchlistCount.text = resources.getQuantityString(
                                R.plurals.watchlist_stock_count,
                                state.items.size,
                                state.items.size
                            )
                        }
                    }
                }
            }
        }
    }

    private fun observeMessages() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.messages.collect { message ->
                    Toast.makeText(requireContext(), message, Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    override fun onStart() {
        super.onStart()
        viewModel.setLiveUpdatesActive(true)
    }

    override fun onStop() {
        viewModel.setLiveUpdatesActive(false)
        super.onStop()
    }

    override fun onDestroyView() {
        binding.rvWatchlist.adapter = null
        _binding = null
        super.onDestroyView()
    }
}
