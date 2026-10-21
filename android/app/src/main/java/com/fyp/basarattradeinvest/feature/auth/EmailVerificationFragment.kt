package com.fyp.basarattradeinvest.feature.auth

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.NavOptions
import androidx.navigation.fragment.findNavController
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentEmailVerificationBinding
import kotlinx.coroutines.launch

class EmailVerificationFragment : Fragment() {

    private var _binding: FragmentEmailVerificationBinding? = null
    private val binding get() = _binding!!

    private val viewModel: EmailVerificationViewModel by viewModels()
    private lateinit var otpHelper: OtpInputHelper
    private var email: String = ""

    companion object {
        const val ARG_EMAIL = "arg_email"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        email = arguments?.getString(ARG_EMAIL).orEmpty()
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentEmailVerificationBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        binding.tvEmailDisplay.text = email

        setupOtpInput()
        setupClickListeners()
        observeState()
    }

    private fun setupOtpInput() {
        val editTexts = listOf(
            binding.etOtp1,
            binding.etOtp2,
            binding.etOtp3,
            binding.etOtp4,
            binding.etOtp5,
            binding.etOtp6
        )

        otpHelper = OtpInputHelper(editTexts) { code, isComplete ->
            binding.btnVerify.isEnabled = isComplete
            binding.btnVerify.alpha = if (isComplete) 1.0f else 0.6f
        }

        binding.btnVerify.isEnabled = false
        binding.btnVerify.alpha = 0.6f
    }

    private fun setupClickListeners() {
        binding.btnBack.setOnClickListener {
            findNavController().navigateUp()
        }

        binding.btnVerify.setOnClickListener {
            val code = otpHelper.getCode()
            viewModel.verifyEmail(email, code)
        }

        binding.tvResendAction.setOnClickListener {
            viewModel.resendVerification(email)
        }
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                // Observe Main Verification UI State
                launch {
                    viewModel.uiState.collect { state ->
                        when (state) {
                            is AuthUiState.Idle -> {
                                binding.pbLoading.visibility = View.GONE
                                binding.tvVerifyLabel.visibility = View.VISIBLE
                                otpHelper.setEnabled(true)
                            }
                            is AuthUiState.Loading -> {
                                binding.pbLoading.visibility = View.VISIBLE
                                binding.tvVerifyLabel.visibility = View.GONE
                                binding.btnVerify.isEnabled = false
                                otpHelper.setEnabled(false)
                            }
                            is AuthUiState.Success -> {
                                binding.pbLoading.visibility = View.GONE
                                binding.tvVerifyLabel.visibility = View.VISIBLE
                                Toast.makeText(
                                    requireContext(),
                                    state.message ?: "Email verified successfully!",
                                    Toast.LENGTH_SHORT
                                ).show()

                                val navOptions = NavOptions.Builder()
                                    .setPopUpTo(R.id.nav_graph, true)
                                    .build()
                                findNavController().navigate(R.id.nav_home, null, navOptions)
                                viewModel.resetState()
                            }
                            is AuthUiState.Error -> {
                                binding.pbLoading.visibility = View.GONE
                                binding.tvVerifyLabel.visibility = View.VISIBLE
                                binding.btnVerify.isEnabled = otpHelper.getCode().length == 6
                                otpHelper.setEnabled(true)
                                Toast.makeText(requireContext(), state.message, Toast.LENGTH_LONG).show()
                                viewModel.resetState()
                            }
                        }
                    }
                }

                // Observe Cooldown Timer
                launch {
                    viewModel.cooldownSeconds.collect { remaining ->
                        if (remaining > 0) {
                            binding.tvResendAction.isEnabled = false
                            binding.tvResendAction.setTextColor(
                                ContextCompat.getColor(requireContext(), R.color.color_text_secondary)
                            )
                            binding.tvResendTimer.visibility = View.VISIBLE
                            val min = remaining / 60
                            val sec = remaining % 60
                            binding.tvResendTimer.text = String.format("(%02d:%02d)", min, sec)
                        } else {
                            binding.tvResendAction.isEnabled = true
                            binding.tvResendAction.setTextColor(
                                ContextCompat.getColor(requireContext(), R.color.color_brand_green)
                            )
                            binding.tvResendTimer.visibility = View.GONE
                        }
                    }
                }

                // Observe Resend Feedback
                launch {
                    viewModel.resendFeedback.collect { feedback ->
                        if (feedback != null) {
                            Toast.makeText(requireContext(), feedback, Toast.LENGTH_SHORT).show()
                            viewModel.clearResendFeedback()
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
