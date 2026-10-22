package com.fyp.basarattradeinvest.feature.etf

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentEtfDirectoryBinding
import com.fyp.basarattradeinvest.domain.model.etf.EtfItem
import com.fyp.basarattradeinvest.feature.etf.adapter.EtfListAdapter
import kotlinx.coroutines.launch

class EtfDirectoryFragment : Fragment() {

    private var _binding: FragmentEtfDirectoryBinding? = null
    private val binding get() = _binding!!

    private val viewModel: EtfDirectoryViewModel by activityViewModels()

    private val adapter by lazy { EtfListAdapter { etf -> openDetail(etf) } }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentEtfDirectoryBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        binding.ivBack.setOnClickListener { findNavController().popBackStack() }

        binding.rvEtfs.layoutManager = LinearLayoutManager(requireContext())
        binding.rvEtfs.adapter = adapter

        binding.swipeRefresh.setOnRefreshListener { viewModel.load() }
        binding.btnRetry.setOnClickListener { viewModel.load() }

        observeState()
        viewModel.ensureLoaded()
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    binding.swipeRefresh.isRefreshing = false
                    when (state) {
                        is EtfDirectoryUiState.Loading -> {
                            render(true, false, false, false)
                            binding.layoutSummary.visibility = View.GONE
                        }

                        is EtfDirectoryUiState.Success -> {
                            render(false, true, false, false)
                            binding.layoutSummary.visibility = View.VISIBLE
                            binding.tvSummaryTotal.text = state.total.toString()
                            binding.tvSummaryShariah.text = state.shariahCount.toString()
                            binding.tvSummaryConventional.text = state.conventionalCount.toString()
                            adapter.submitList(state.etfs)
                        }

                        is EtfDirectoryUiState.Empty -> {
                            render(false, false, true, false)
                            binding.layoutSummary.visibility = View.GONE
                        }

                        is EtfDirectoryUiState.Error -> {
                            render(false, false, false, true)
                            binding.layoutSummary.visibility = View.GONE
                            binding.tvErrorMessage.text = state.message
                        }
                    }
                }
            }
        }
    }

    private fun render(skeleton: Boolean, list: Boolean, empty: Boolean, error: Boolean) {
        val v = View.VISIBLE
        val g = View.GONE
        binding.layoutSkeleton.visibility = if (skeleton) v else g
        binding.rvEtfs.visibility = if (list) v else g
        binding.layoutEmpty.visibility = if (empty) v else g
        binding.layoutError.visibility = if (error) v else g
    }

    private fun openDetail(etf: EtfItem) {
        val bundle = Bundle().apply { putString("symbol", etf.symbol) }
        findNavController().navigate(R.id.etfDetailFragment, bundle)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
