package com.fyp.basarattradeinvest.feature.auth

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
import com.fyp.basarattradeinvest.databinding.FragmentResetPasswordBinding
import kotlinx.coroutines.launch

class ResetPasswordFragment : Fragment() {

    private var _binding: FragmentResetPasswordBinding? = null
    private val binding get() = _binding!!

    private val viewModel: ResetPasswordViewModel by viewModels()

    private var isNewPasswordVisible = false
    private var isConfirmPasswordVisible = false
    private var resetToken: String = ""

    companion object {
        const val ARG_RESET_TOKEN = "arg_reset_token"
        const val ARG_EMAIL = "arg_email"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        resetToken = arguments?.getString(ARG_RESET_TOKEN).orEmpty()
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentResetPasswordBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupPasswordToggles()
        setupClickListeners()
        observeUiState()
    }

    private fun setupPasswordToggles() {
        binding.ivToggleNewPassword.setOnClickListener {
            isNewPasswordVisible = !isNewPasswordVisible
            if (isNewPasswordVisible) {
                binding.etNewPassword.transformationMethod = HideReturnsTransformationMethod.getInstance()
                binding.ivToggleNewPassword.setImageResource(R.drawable.ic_eye_off)
            } else {
                binding.etNewPassword.transformationMethod = PasswordTransformationMethod.getInstance()
                binding.ivToggleNewPassword.setImageResource(R.drawable.ic_eye)
            }
            binding.etNewPassword.setSelection(binding.etNewPassword.text?.length ?: 0)
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
            binding.etConfirmPassword.setSelection(binding.etConfirmPassword.text?.length ?: 0)
        }
    }

    private fun setupClickListeners() {
        binding.btnBack.setOnClickListener {
            findNavController().navigateUp()
        }

        binding.btnResetPassword.setOnClickListener {
            val newPassword = binding.etNewPassword.text?.toString().orEmpty()
            val confirmPassword = binding.etConfirmPassword.text?.toString().orEmpty()
            viewModel.resetPassword(resetToken, newPassword, confirmPassword)
        }
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is AuthUiState.Idle -> {
                            binding.pbLoading.visibility = View.GONE
                            binding.tvResetLabel.visibility = View.VISIBLE
                            binding.btnResetPassword.isEnabled = true
                        }
                        is AuthUiState.Loading -> {
                            binding.pbLoading.visibility = View.VISIBLE
                            binding.tvResetLabel.visibility = View.GONE
                            binding.btnResetPassword.isEnabled = false
                        }
                        is AuthUiState.Success -> {
                            binding.pbLoading.visibility = View.GONE
                            binding.tvResetLabel.visibility = View.VISIBLE
                            binding.btnResetPassword.isEnabled = true
                            Toast.makeText(
                                requireContext(),
                                state.message ?: "Password reset successfully! Please sign in.",
                                Toast.LENGTH_LONG
                            ).show()
                            findNavController().navigate(R.id.action_resetPasswordFragment_to_loginFragment)
                            viewModel.resetState()
                        }
                        is AuthUiState.Error -> {
                            binding.pbLoading.visibility = View.GONE
                            binding.tvResetLabel.visibility = View.VISIBLE
                            binding.btnResetPassword.isEnabled = true
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
