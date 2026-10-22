package com.fyp.basarattradeinvest.feature.recommendation.list

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentRecommendationsBinding
import kotlinx.coroutines.launch

class RecommendationsFragment : Fragment() {

    private var _binding: FragmentRecommendationsBinding? = null
    private val binding get() = _binding!!

    private val viewModel: RecommendationsViewModel by activityViewModels()
    private lateinit var adapter: RecommendationsAdapter

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentRecommendationsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupRecyclerView()
        setupListeners()
        observeUiState()
    }

    private fun setupRecyclerView() {
        adapter = RecommendationsAdapter { item ->
            val bundle = Bundle().apply {
                putString("symbol", item.symbol)
            }
            findNavController().navigate(R.id.action_recommendations_to_detail, bundle)
        }

        binding.rvRecommendations.layoutManager = LinearLayoutManager(requireContext())
        binding.rvRecommendations.adapter = adapter
    }

    private fun setupListeners() {
        binding.ivBack.setOnClickListener {
            findNavController().popBackStack()
        }

        binding.ivSettings.setOnClickListener {
            findNavController().navigate(R.id.recommendationSettingsFragment)
        }

        binding.swipeRefresh.setOnRefreshListener {
            viewModel.retry()
        }

        binding.btnRetry.setOnClickListener {
            viewModel.retry()
        }

        // Risk profile pills
        binding.pillRiskConservative.setOnClickListener {
            viewModel.setRiskProfile("conservative")
        }
        binding.pillRiskModerate.setOnClickListener {
            viewModel.setRiskProfile("moderate")
        }
        binding.pillRiskAggressive.setOnClickListener {
            viewModel.setRiskProfile("aggressive")
        }
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    renderUiState(state)
                }
            }
        }
    }

    private fun renderUiState(state: RecommendationsUiState) {
        binding.layoutLoading.visibility = View.GONE
        binding.layoutEmpty.visibility = View.GONE
        binding.layoutError.visibility = View.GONE
        binding.rvRecommendations.visibility = View.GONE

        when (state) {
            is RecommendationsUiState.Loading -> {
                if (!binding.swipeRefresh.isRefreshing) {
                    binding.layoutLoading.visibility = View.VISIBLE
                }
            }
            is RecommendationsUiState.Success -> {
                binding.swipeRefresh.isRefreshing = false
                binding.rvRecommendations.visibility = View.VISIBLE
                adapter.submitList(state.recommendations)
                updateRiskPills(state.selectedRiskProfile)
            }
            is RecommendationsUiState.Empty -> {
                binding.swipeRefresh.isRefreshing = false
                binding.layoutEmpty.visibility = View.VISIBLE
                updateRiskPills(state.selectedRiskProfile)
            }
            is RecommendationsUiState.Error -> {
                binding.swipeRefresh.isRefreshing = false
                binding.layoutError.visibility = View.VISIBLE
                binding.tvErrorMessage.text = state.message
            }
        }
    }

    private fun updateRiskPills(selectedProfile: String) {
        val selectedBg = R.drawable.bg_chip_filter_selected
        val unselectedBg = R.drawable.bg_chip_filter_unselected
        val selectedColor = ContextCompat.getColor(requireContext(), R.color.color_positive)
        val unselectedColor = ContextCompat.getColor(requireContext(), R.color.color_text_secondary)

        binding.pillRiskConservative.setBackgroundResource(if (selectedProfile == "conservative") selectedBg else unselectedBg)
        binding.pillRiskConservative.setTextColor(if (selectedProfile == "conservative") selectedColor else unselectedColor)

        binding.pillRiskModerate.setBackgroundResource(if (selectedProfile == "moderate") selectedBg else unselectedBg)
        binding.pillRiskModerate.setTextColor(if (selectedProfile == "moderate") selectedColor else unselectedColor)

        binding.pillRiskAggressive.setBackgroundResource(if (selectedProfile == "aggressive") selectedBg else unselectedBg)
        binding.pillRiskAggressive.setTextColor(if (selectedProfile == "aggressive") selectedColor else unselectedColor)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
