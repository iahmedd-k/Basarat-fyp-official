package com.fyp.basarattradeinvest.feature.auth

import android.graphics.Typeface
import android.os.Bundle
import android.text.SpannableString
import android.text.Spanned
import android.text.method.HideReturnsTransformationMethod
import android.text.method.PasswordTransformationMethod
import android.text.style.ForegroundColorSpan
import android.text.style.StyleSpan
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.core.os.bundleOf
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.navigation.navOptions
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.core.session.SessionManager
import com.fyp.basarattradeinvest.databinding.FragmentLoginBinding
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.launch

class LoginFragment : Fragment() {

    private var _binding: FragmentLoginBinding? = null
    private val binding get() = _binding!!

    private val viewModel: LoginViewModel by viewModels()
    private var isPasswordVisible = false
    private var isGoogleSignInInFlight = false

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentLoginBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        styleTitle()
        setupPasswordVisibilityToggle()
        setupBottomLink()
        setupClickListeners()
        observeUiState()
    }

    private fun styleTitle() {
        val title = getString(R.string.welcome_back_title)
        val spannable = SpannableString(title)
        val accentStart = title.lastIndexOf("Back")
        if (accentStart >= 0) {
            val accent = ContextCompat.getColor(requireContext(), R.color.color_basarat_green)
            spannable.setSpan(
                ForegroundColorSpan(accent),
                accentStart,
                title.length,
                Spanned.SPAN_EXCLUSIVE_EXCLUSIVE
            )
        }
        binding.tvTitle.text = spannable
    }

    private fun setupPasswordVisibilityToggle() {
        binding.ivTogglePassword.setOnClickListener {
            isPasswordVisible = !isPasswordVisible
            if (isPasswordVisible) {
                binding.etPassword.transformationMethod = HideReturnsTransformationMethod.getInstance()
                binding.ivTogglePassword.setImageResource(R.drawable.ic_eye_off)
            } else {
                binding.etPassword.transformationMethod = PasswordTransformationMethod.getInstance()
                binding.ivTogglePassword.setImageResource(R.drawable.ic_eye)
            }
            binding.etPassword.setSelection(binding.etPassword.text?.length ?: 0)
        }
    }

    private fun setupBottomLink() {
        val fullText = "${getString(R.string.dont_have_account)} ${getString(R.string.sign_up)}"
        val spannable = SpannableString(fullText)

        val signUpStart = fullText.indexOf(getString(R.string.sign_up))
        if (signUpStart != -1) {
            val signUpEnd = signUpStart + getString(R.string.sign_up).length
            val accentColor = ContextCompat.getColor(requireContext(), R.color.color_basarat_green)
            spannable.setSpan(ForegroundColorSpan(accentColor), signUpStart, signUpEnd, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            spannable.setSpan(StyleSpan(Typeface.BOLD), signUpStart, signUpEnd, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }

        binding.tvSignUpLink.text = spannable
        binding.tvSignUpLink.setOnClickListener {
            findNavController().navigate(R.id.action_loginFragment_to_signUpFragment)
        }
    }

    private fun setupClickListeners() {
        binding.btnSignIn.setOnClickListener {
            val email = binding.etEmail.text?.toString().orEmpty().trim()
            val password = binding.etPassword.text?.toString().orEmpty()
            viewModel.signIn(email, password)
        }

        binding.tvForgotPassword.setOnClickListener {
            findNavController().navigate(R.id.action_loginFragment_to_forgotPasswordFragment)
        }

        binding.btnGoogleSignIn.setOnClickListener { startGoogleSignIn() }
    }

    private fun startGoogleSignIn() {
        if (isGoogleSignInInFlight) return
        isGoogleSignInInFlight = true
        setGoogleSigningIn(true)

        val activity = requireActivity()
        viewLifecycleOwner.lifecycleScope.launch {
            val idToken = GoogleSignInLauncher.requestIdToken(activity).fold(
                onSuccess = { token ->
                    if (token == null) finishGoogleSignIn() // User backed out of the picker.
                    token
                },
                onFailure = { error ->
                    finishGoogleSignIn()
                    _binding?.let {
                        Toast.makeText(requireContext(), error.message, Toast.LENGTH_LONG).show()
                    }
                    null
                }
            )
            if (idToken != null) viewModel.signInWithGoogle(idToken)
        }
    }

    private fun finishGoogleSignIn() {
        isGoogleSignInInFlight = false
        _binding?.let { setGoogleSigningIn(false) }
    }

    private fun setGoogleSigningIn(signingIn: Boolean) {
        binding.pbGoogleLoading.visibility = if (signingIn) View.VISIBLE else View.GONE
        binding.ivGoogleIcon.visibility = if (signingIn) View.INVISIBLE else View.VISIBLE
        binding.tvGoogleLabel.visibility = if (signingIn) View.INVISIBLE else View.VISIBLE
        binding.btnGoogleSignIn.isEnabled = !signingIn
        binding.btnSignIn.isEnabled = !signingIn
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is AuthUiState.Idle -> {
                            binding.pbLoading.visibility = View.GONE
                            binding.tvSignInLabel.visibility = View.VISIBLE
                            binding.btnSignIn.isEnabled = true
                        }
                        is AuthUiState.Loading -> {
                            if (!isGoogleSignInInFlight) {
                                binding.pbLoading.visibility = View.VISIBLE
                                binding.tvSignInLabel.visibility = View.GONE
                            }
                            binding.btnSignIn.isEnabled = false
                        }
                        is AuthUiState.Success -> {
                            finishGoogleSignIn()
                            binding.pbLoading.visibility = View.GONE
                            binding.tvSignInLabel.visibility = View.VISIBLE
                            binding.btnSignIn.isEnabled = true
                            val pendingDestination = SessionManager.consumePostLoginDestination()
                            if (pendingDestination == null) {
                                findNavController().navigate(R.id.action_loginFragment_to_homeFragment)
                            } else {
                                findNavController().navigate(
                                    pendingDestination.destinationId,
                                    pendingDestination.arguments,
                                    navOptions {
                                        popUpTo(R.id.loginFragment) { inclusive = true }
                                        launchSingleTop = true
                                    }
                                )
                            }
                            viewModel.resetState()
                        }
                        is AuthUiState.Error -> {
                            finishGoogleSignIn()
                            binding.pbLoading.visibility = View.GONE
                            binding.tvSignInLabel.visibility = View.VISIBLE
                            binding.btnSignIn.isEnabled = true

                            if (state.message.contains("Email not verified", ignoreCase = true)) {
                                val enteredEmail = binding.etEmail.text?.toString().orEmpty().trim()
                                MaterialAlertDialogBuilder(requireContext())
                                    .setTitle("Email Verification Required")
                                    .setMessage(state.message)
                                    .setPositiveButton("Verify Now") { _, _ ->
                                        val bundle = bundleOf(EmailVerificationFragment.ARG_EMAIL to enteredEmail)
                                        findNavController().navigate(
                                            R.id.action_loginFragment_to_emailVerificationFragment,
                                            bundle
                                        )
                                    }
                                    .setNegativeButton("Cancel", null)
                                    .show()
                            } else {
                                Toast.makeText(requireContext(), state.message, Toast.LENGTH_LONG).show()
                            }
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
