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
import com.fyp.basarattradeinvest.databinding.FragmentIpoCalendarBinding
import com.fyp.basarattradeinvest.feature.ipo.adapter.IpoCalendarAdapter
import kotlinx.coroutines.launch

class IpoCalendarFragment : Fragment() {

    private var _binding: FragmentIpoCalendarBinding? = null
    private val binding get() = _binding!!

    private val viewModel: IpoViewModel by activityViewModels()

    private val adapter by lazy { IpoCalendarAdapter() }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentIpoCalendarBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        binding.rvCalendar.layoutManager = LinearLayoutManager(requireContext())
        binding.rvCalendar.adapter = adapter

        binding.swipeRefresh.setOnRefreshListener { viewModel.loadCalendar() }
        binding.btnRetry.setOnClickListener { viewModel.loadCalendar() }

        observeState()
        viewModel.ensureCalendarLoaded()
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.calendarState.collect { state ->
                    binding.swipeRefresh.isRefreshing = false
                    when (state) {
                        is IpoCalendarUiState.Loading -> render(true, false, false, false)

                        is IpoCalendarUiState.Success -> {
                            render(false, true, false, false)
                            adapter.submitList(state.events)
                            val count = state.events.size
                            binding.tvCalendarSummary.visibility = View.VISIBLE
                            binding.tvCalendarSummary.text =
                                if (count == 1) "1 upcoming milestone" else "$count upcoming milestones"
                        }

                        is IpoCalendarUiState.Empty -> {
                            render(false, false, true, false)
                            binding.tvCalendarSummary.visibility = View.GONE
                        }

                        is IpoCalendarUiState.Error -> {
                            render(false, false, false, true)
                            binding.tvCalendarSummary.visibility = View.GONE
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
        binding.rvCalendar.visibility = if (list) v else g
        binding.layoutEmpty.visibility = if (empty) v else g
        binding.layoutError.visibility = if (error) v else g
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
