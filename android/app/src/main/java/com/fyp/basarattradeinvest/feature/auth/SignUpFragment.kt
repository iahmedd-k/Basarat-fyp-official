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
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentSignUpBinding
import kotlinx.coroutines.launch

class SignUpFragment : Fragment() {

    private var _binding: FragmentSignUpBinding? = null
    private val binding get() = _binding!!

    private val viewModel: SignUpViewModel by viewModels()
    private var isPasswordVisible = false
    private var isConfirmPasswordVisible = false
    private var isGoogleSignInInFlight = false

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentSignUpBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        styleTitle()
        binding.ivBack.setOnClickListener { findNavController().navigateUp() }
        setupPasswordVisibilityToggle()
        setupBottomLink()
        setupClickListeners()
        observeUiState()
    }

    private fun styleTitle() {
        val title = getString(R.string.signup_title)
        val spannable = SpannableString(title)
        val accentStart = title.lastIndexOf("Account")
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

    private fun setupBottomLink() {
        val fullText = "${getString(R.string.already_have_account)} ${getString(R.string.sign_in)}"
        val spannable = SpannableString(fullText)

        val signInStart = fullText.indexOf(getString(R.string.sign_in))
        if (signInStart != -1) {
            val signInEnd = signInStart + getString(R.string.sign_in).length
            val accentColor = ContextCompat.getColor(requireContext(), R.color.color_basarat_green)
            spannable.setSpan(ForegroundColorSpan(accentColor), signInStart, signInEnd, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            spannable.setSpan(StyleSpan(Typeface.BOLD), signInStart, signInEnd, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }

        binding.tvSignInLink.text = spannable
        binding.tvSignInLink.setOnClickListener {
            findNavController().navigate(R.id.action_signUpFragment_to_loginFragment)
        }
    }

    private fun setupClickListeners() {
        binding.btnSignUp.setOnClickListener {
            val name = binding.etName.text?.toString().orEmpty().trim()
            val email = binding.etEmail.text?.toString().orEmpty().trim()
            val password = binding.etPassword.text?.toString().orEmpty()
            val confirmPassword = binding.etConfirmPassword.text?.toString().orEmpty()
            viewModel.signUp(name, email, password, confirmPassword)
        }

        binding.btnGoogleSignUp.setOnClickListener { startGoogleSignIn() }
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
        binding.btnGoogleSignUp.isEnabled = !signingIn
        binding.btnSignUp.isEnabled = !signingIn
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is AuthUiState.Idle -> {
                            binding.pbLoading.visibility = View.GONE
                            binding.tvSignUpLabel.visibility = View.VISIBLE
                            binding.btnSignUp.isEnabled = true
                        }
                        is AuthUiState.Loading -> {
                            if (!isGoogleSignInInFlight) {
                                binding.pbLoading.visibility = View.VISIBLE
                                binding.tvSignUpLabel.visibility = View.GONE
                            }
                            binding.btnSignUp.isEnabled = false
                        }
                        is AuthUiState.Success -> {
                            finishGoogleSignIn()
                            binding.pbLoading.visibility = View.GONE
                            binding.tvSignUpLabel.visibility = View.VISIBLE
                            binding.btnSignUp.isEnabled = true

                            if (state.isAuthenticated) {
                                // Google-verified accounts arrive with tokens already issued,
                                // so there is no email-confirmation step to walk through.
                                findNavController().navigate(R.id.action_signUpFragment_to_homeFragment)
                                viewModel.resetState()
                                return@collect
                            }

                            Toast.makeText(
                                requireContext(),
                                state.message ?: "Account created! Please check your email for the verification code.",
                                Toast.LENGTH_LONG
                            ).show()

                            val targetEmail = state.userEmail ?: binding.etEmail.text?.toString().orEmpty().trim()
                            val bundle = bundleOf(EmailVerificationFragment.ARG_EMAIL to targetEmail)
                            findNavController().navigate(R.id.action_signUpFragment_to_emailVerificationFragment, bundle)
                            viewModel.resetState()
                        }
                        is AuthUiState.Error -> {
                            finishGoogleSignIn()
                            binding.pbLoading.visibility = View.GONE
                            binding.tvSignUpLabel.visibility = View.VISIBLE
                            binding.btnSignUp.isEnabled = true
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
