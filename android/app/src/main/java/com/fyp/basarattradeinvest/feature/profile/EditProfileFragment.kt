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
import com.fyp.basarattradeinvest.databinding.FragmentEditProfileBinding
import com.fyp.basarattradeinvest.feature.auth.AuthUiState
import kotlinx.coroutines.launch

class EditProfileFragment : Fragment() {

    private var _binding: FragmentEditProfileBinding? = null
    private val binding get() = _binding!!

    private val viewModel: EditProfileViewModel by viewModels()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentEditProfileBinding.inflate(inflater, container, false)
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

        binding.btnSave.setOnClickListener {
            val name = binding.etFullName.text?.toString().orEmpty()
            val avatarUrl = binding.etAvatarUrl.text?.toString().orEmpty()
            viewModel.saveProfile(name, avatarUrl)
        }
    }

    private fun observeData() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                // Pre-populate input fields once
                launch {
                    viewModel.currentProfile.collect { profile ->
                        if (profile != null && binding.etFullName.text.isNullOrBlank()) {
                            binding.etFullName.setText(profile.fullName.orEmpty())
                            binding.etAvatarUrl.setText(profile.avatarUrl.orEmpty())
                        }
                    }
                }

                // Collect Submission State
                launch {
                    viewModel.uiState.collect { state ->
                        when (state) {
                            is AuthUiState.Idle -> {
                                binding.pbLoading.visibility = View.GONE
                                binding.tvSaveLabel.visibility = View.VISIBLE
                                binding.btnSave.isEnabled = true
                            }
                            is AuthUiState.Loading -> {
                                binding.pbLoading.visibility = View.VISIBLE
                                binding.tvSaveLabel.visibility = View.GONE
                                binding.btnSave.isEnabled = false
                            }
                            is AuthUiState.Success -> {
                                binding.pbLoading.visibility = View.GONE
                                binding.tvSaveLabel.visibility = View.VISIBLE
                                binding.btnSave.isEnabled = true
                                Toast.makeText(
                                    requireContext(),
                                    state.message ?: "Profile updated successfully!",
                                    Toast.LENGTH_SHORT
                                ).show()
                                viewModel.resetState()
                                findNavController().navigateUp()
                            }
                            is AuthUiState.Error -> {
                                binding.pbLoading.visibility = View.GONE
                                binding.tvSaveLabel.visibility = View.VISIBLE
                                binding.btnSave.isEnabled = true
                                Toast.makeText(requireContext(), state.message, Toast.LENGTH_LONG).show()
                                viewModel.resetState()
                            }
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
