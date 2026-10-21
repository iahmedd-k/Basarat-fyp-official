package com.fyp.basarattradeinvest.feature.profile

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import com.fyp.basarattradeinvest.databinding.FragmentNotificationPreferencesBinding
import kotlinx.coroutines.launch

class NotificationPreferencesFragment : Fragment() {

    private var _binding: FragmentNotificationPreferencesBinding? = null
    private val binding get() = _binding!!

    private val viewModel: NotificationPreferencesViewModel by viewModels()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentNotificationPreferencesBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupClickListeners()
        observeData()
    }

    private fun setupClickListeners() {
        binding.btnBack.setOnClickListener {
            findNavController().navigateUp()
        }

        binding.btnSavePreferences.setOnClickListener {
            val selectedChannels = mutableListOf<String>()
            if (binding.switchChannelPush.isChecked) selectedChannels.add("push")
            if (binding.switchChannelInApp.isChecked) selectedChannels.add("in_app")
            if (binding.switchChannelEmail.isChecked) selectedChannels.add("email")

            val selectedCategories = mutableListOf<String>()
            if (binding.switchCatLikes.isChecked) selectedCategories.add("POST_LIKED")
            if (binding.switchCatComments.isChecked) selectedCategories.add("POST_COMMENTED")
            if (binding.switchCatReplies.isChecked) selectedCategories.add("COMMENT_REPLIED")
            if (binding.switchCatFollowers.isChecked) selectedCategories.add("USER_FOLLOWED")

            viewModel.savePreferences(
                channels = selectedChannels,
                categories = selectedCategories
            )
        }
    }

    private fun observeData() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is NotificationPrefsUiState.Idle -> {
                            binding.pbSaving.visibility = View.GONE
                            binding.tvSaveLabel.visibility = View.VISIBLE
                            binding.btnSavePreferences.isEnabled = true
                        }
                        is NotificationPrefsUiState.Loading -> {
                            binding.pbSaving.visibility = View.VISIBLE
                            binding.tvSaveLabel.visibility = View.GONE
                            binding.btnSavePreferences.isEnabled = false
                        }
                        is NotificationPrefsUiState.Success -> {
                            binding.pbSaving.visibility = View.GONE
                            binding.tvSaveLabel.visibility = View.VISIBLE
                            binding.btnSavePreferences.isEnabled = true
                            Toast.makeText(
                                requireContext(),
                                state.message,
                                Toast.LENGTH_SHORT
                            ).show()
                            viewModel.resetState()
                            findNavController().navigateUp()
                        }
                        is NotificationPrefsUiState.Error -> {
                            binding.pbSaving.visibility = View.GONE
                            binding.tvSaveLabel.visibility = View.VISIBLE
                            binding.btnSavePreferences.isEnabled = true
                            Toast.makeText(requireContext(), state.message, Toast.LENGTH_LONG).show()
                            viewModel.resetState()
                        }
                    }
                }
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
