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
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentIpoDirectoryBinding
import com.fyp.basarattradeinvest.domain.model.ipo.IpoItem
import com.fyp.basarattradeinvest.feature.ipo.adapter.IpoListAdapter
import kotlinx.coroutines.launch

class IpoDirectoryFragment : Fragment() {

    private var _binding: FragmentIpoDirectoryBinding? = null
    private val binding get() = _binding!!

    private val viewModel: IpoViewModel by activityViewModels()

    private val adapter by lazy { IpoListAdapter { ipo -> openDetail(ipo) } }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentIpoDirectoryBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        binding.rvIpos.layoutManager = LinearLayoutManager(requireContext())
        binding.rvIpos.adapter = adapter

        binding.swipeRefresh.setOnRefreshListener { viewModel.loadDirectory() }
        binding.btnRetry.setOnClickListener { viewModel.loadDirectory() }

        observeState()
        viewModel.ensureDirectoryLoaded()
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.directoryState.collect { state ->
                    binding.swipeRefresh.isRefreshing = false
                    when (state) {
                        is IpoDirectoryUiState.Loading -> render(
                            skeleton = true, list = false, empty = false, error = false
                        )

                        is IpoDirectoryUiState.Success -> {
                            render(skeleton = false, list = true, empty = false, error = false)
                            adapter.submitList(state.items)
                        }

                        is IpoDirectoryUiState.Empty -> render(
                            skeleton = false, list = false, empty = true, error = false
                        )

                        is IpoDirectoryUiState.Error -> {
                            render(skeleton = false, list = false, empty = false, error = true)
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
        binding.rvIpos.visibility = if (list) v else g
        binding.layoutEmpty.visibility = if (empty) v else g
        binding.layoutError.visibility = if (error) v else g
    }

    private fun openDetail(ipo: IpoItem) {
        val bundle = Bundle().apply { putString("symbol", ipo.symbol) }
        findNavController().navigate(R.id.ipoDetailFragment, bundle)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
