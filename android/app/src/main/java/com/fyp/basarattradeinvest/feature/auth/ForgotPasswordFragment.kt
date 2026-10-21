package com.fyp.basarattradeinvest.feature.auth

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.core.os.bundleOf
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentForgotPasswordBinding
import kotlinx.coroutines.launch

class ForgotPasswordFragment : Fragment() {

    private var _binding: FragmentForgotPasswordBinding? = null
    private val binding get() = _binding!!

    private val viewModel: ForgotPasswordViewModel by viewModels()
    private var lastEnteredEmail: String = ""

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentForgotPasswordBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupClickListeners()
        observeUiState()
    }

    private fun setupClickListeners() {
        binding.btnBack.setOnClickListener {
            findNavController().navigateUp()
        }

        binding.btnSubmit.setOnClickListener {
            val email = binding.etEmail.text?.toString().orEmpty().trim()
            lastEnteredEmail = email
            viewModel.requestPasswordReset(email)
        }

        binding.tvHaveTokenLink.setOnClickListener {
            val email = binding.etEmail.text?.toString().orEmpty().trim()
            val bundle = bundleOf(VerifyResetCodeFragment.ARG_EMAIL to email)
            findNavController().navigate(R.id.action_forgotPasswordFragment_to_verifyResetCodeFragment, bundle)
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
                            binding.btnSubmit.isEnabled = true
                        }
                        is AuthUiState.Loading -> {
                            binding.pbLoading.visibility = View.VISIBLE
                            binding.tvSubmitLabel.visibility = View.GONE
                            binding.btnSubmit.isEnabled = false
                        }
                        is AuthUiState.Success -> {
                            binding.pbLoading.visibility = View.GONE
                            binding.tvSubmitLabel.visibility = View.VISIBLE
                            binding.btnSubmit.isEnabled = true
                            Toast.makeText(
                                requireContext(),
                                state.message ?: "Reset code sent to your email.",
                                Toast.LENGTH_SHORT
                            ).show()
                            
                            val bundle = bundleOf(
                                VerifyResetCodeFragment.ARG_EMAIL to (state.userEmail ?: lastEnteredEmail)
                            )
                            findNavController().navigate(
                                R.id.action_forgotPasswordFragment_to_verifyResetCodeFragment,
                                bundle
                            )
                            viewModel.resetState()
                        }
                        is AuthUiState.Error -> {
                            binding.pbLoading.visibility = View.GONE
                            binding.tvSubmitLabel.visibility = View.VISIBLE
                            binding.btnSubmit.isEnabled = true
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
