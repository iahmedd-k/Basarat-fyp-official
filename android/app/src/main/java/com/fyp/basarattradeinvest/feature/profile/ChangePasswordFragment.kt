package com.fyp.basarattradeinvest.feature.profile

import android.os.Bundle
import android.text.method.HideReturnsTransformationMethod
import android.text.method.PasswordTransformationMethod
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
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentChangePasswordBinding
import com.fyp.basarattradeinvest.feature.auth.AuthUiState
import kotlinx.coroutines.launch

class ChangePasswordFragment : Fragment() {

    private var _binding: FragmentChangePasswordBinding? = null
    private val binding get() = _binding!!

    private val viewModel: ChangePasswordViewModel by viewModels()

    private var isCurrentPasswordVisible = false
    private var isNewPasswordVisible = false
    private var isConfirmPasswordVisible = false

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentChangePasswordBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupPasswordToggles()
        setupClickListeners()
        observeUiState()
    }

    private fun setupPasswordToggles() {
        binding.ivToggleCurrentPassword.setOnClickListener {
            isCurrentPasswordVisible = !isCurrentPasswordVisible
            if (isCurrentPasswordVisible) {
                binding.etCurrentPassword.transformationMethod = HideReturnsTransformationMethod.getInstance()
                binding.ivToggleCurrentPassword.setImageResource(R.drawable.ic_eye_off)
            } else {
                binding.etCurrentPassword.transformationMethod = PasswordTransformationMethod.getInstance()
                binding.ivToggleCurrentPassword.setImageResource(R.drawable.ic_eye)
            }
            binding.etCurrentPassword.setSelection(binding.etCurrentPassword.text.length)
        }

        binding.ivToggleNewPassword.setOnClickListener {
            isNewPasswordVisible = !isNewPasswordVisible
            if (isNewPasswordVisible) {
                binding.etNewPassword.transformationMethod = HideReturnsTransformationMethod.getInstance()
                binding.ivToggleNewPassword.setImageResource(R.drawable.ic_eye_off)
            } else {
                binding.etNewPassword.transformationMethod = PasswordTransformationMethod.getInstance()
                binding.ivToggleNewPassword.setImageResource(R.drawable.ic_eye)
            }
            binding.etNewPassword.setSelection(binding.etNewPassword.text.length)
        }

        binding.ivToggleConfirmPassword.setOnClickListener {
            isConfirmPasswordVisible = !isConfirmPasswordVisible
            if (isConfirmPasswordVisible) {
                binding.etConfirmPassword.transformationMethod = HideReturnsTransformationMethod.getInstance()
                binding.ivToggleConfirmPassword.setImageResource(R.drawable.ic_eye_off)
            } else {
                binding.etConfirmPassword.transformationMethod = PasswordTransformationMethod.getInstance()
                binding.ivToggleConfirmPassword.setImageResource(R.drawable.ic_eye)
            }
            binding.etConfirmPassword.setSelection(binding.etConfirmPassword.text.length)
        }
    }

    private fun setupClickListeners() {
        binding.btnBack.setOnClickListener {
            findNavController().navigateUp()
        }

        binding.btnChangePassword.setOnClickListener {
            val currentPassword = binding.etCurrentPassword.text?.toString().orEmpty()
            val newPassword = binding.etNewPassword.text?.toString().orEmpty()
            val confirmPassword = binding.etConfirmPassword.text?.toString().orEmpty()
            viewModel.changePassword(currentPassword, newPassword, confirmPassword)
        }
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is AuthUiState.Idle -> {
                            binding.pbLoading.visibility = View.GONE
                            binding.tvSubmitLabel.visibility = View.VISIBLE
                            binding.btnChangePassword.isEnabled = true
                        }
                        is AuthUiState.Loading -> {
                            binding.pbLoading.visibility = View.VISIBLE
                            binding.tvSubmitLabel.visibility = View.GONE
                            binding.btnChangePassword.isEnabled = false
                        }
                        is AuthUiState.Success -> {
                            binding.pbLoading.visibility = View.GONE
                            binding.tvSubmitLabel.visibility = View.VISIBLE
                            binding.btnChangePassword.isEnabled = true
                            Toast.makeText(
                                requireContext(),
                                state.message ?: "Password updated successfully!",
                                Toast.LENGTH_SHORT
                            ).show()
                            viewModel.resetState()
                            findNavController().navigateUp()
                        }
                        is AuthUiState.Error -> {
                            binding.pbLoading.visibility = View.GONE
                            binding.tvSubmitLabel.visibility = View.VISIBLE
                            binding.btnChangePassword.isEnabled = true
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
