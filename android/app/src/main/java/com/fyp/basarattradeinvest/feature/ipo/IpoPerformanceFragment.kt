package com.fyp.basarattradeinvest.feature.ipo

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.databinding.FragmentIpoPerformanceBinding
import com.fyp.basarattradeinvest.domain.model.ipo.IpoPerformanceItem
import com.fyp.basarattradeinvest.feature.common.FormatUtils
import com.fyp.basarattradeinvest.feature.ipo.adapter.IpoPerformanceAdapter
import kotlinx.coroutines.launch

class IpoPerformanceFragment : Fragment() {

    private var _binding: FragmentIpoPerformanceBinding? = null
    private val binding get() = _binding!!

    private val viewModel: IpoViewModel by activityViewModels()

    private val topAdapter by lazy { IpoPerformanceAdapter() }
    private val recentAdapter by lazy { IpoPerformanceAdapter() }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentIpoPerformanceBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        binding.rvTopPerformers.layoutManager = LinearLayoutManager(requireContext())
        binding.rvTopPerformers.adapter = topAdapter
        binding.rvRecentListings.layoutManager = LinearLayoutManager(requireContext())
        binding.rvRecentListings.adapter = recentAdapter

        binding.btnRetry.setOnClickListener { viewModel.loadPerformance() }

        observeState()
        viewModel.ensurePerformanceLoaded()
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.performanceState.collect { state ->
                    when (state) {
                        is IpoPerformanceUiState.Loading -> render(true, false, false, false)

                        is IpoPerformanceUiState.Success -> {
                            render(false, true, false, false)
                            val summary = state.summary
                            binding.tvTotalListed.text = summary.totalListed.toString()
                            binding.tvAvgGain.text = FormatUtils.percentSigned(summary.averageListingDayGainPct)
                            bindList(binding.titleTopPerformers, binding.rvTopPerformers, topAdapter, summary.topPerformers)
                            bindList(binding.titleRecentListings, binding.rvRecentListings, recentAdapter, summary.recentListings)
                        }

                        is IpoPerformanceUiState.Empty -> render(false, false, true, false)

                        is IpoPerformanceUiState.Error -> {
                            render(false, false, false, true)
                            binding.tvErrorMessage.text = state.message
                        }
                    }
                }
            }
        }
    }

    private fun bindList(
        title: View,
        recyclerView: View,
        adapter: IpoPerformanceAdapter,
        items: List<IpoPerformanceItem>
    ) {
        if (items.isEmpty()) {
            title.visibility = View.GONE
            recyclerView.visibility = View.GONE
        } else {
            title.visibility = View.VISIBLE
            recyclerView.visibility = View.VISIBLE
            adapter.submitList(items)
        }
    }

    private fun render(skeleton: Boolean, content: Boolean, empty: Boolean, error: Boolean) {
        val v = View.VISIBLE
        val g = View.GONE
        binding.layoutSkeleton.visibility = if (skeleton) v else g
        binding.scrollContent.visibility = if (content) v else g
        binding.layoutEmpty.visibility = if (empty) v else g
        binding.layoutError.visibility = if (error) v else g
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
