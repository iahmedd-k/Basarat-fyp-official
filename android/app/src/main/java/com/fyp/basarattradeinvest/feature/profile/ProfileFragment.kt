package com.fyp.basarattradeinvest.feature.profile

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.NavOptions
import androidx.navigation.fragment.findNavController
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentProfileBinding
import com.fyp.basarattradeinvest.domain.model.auth.UserProfile
import com.fyp.basarattradeinvest.feature.auth.AuthUiState
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.launch
import java.util.Locale

class ProfileFragment : Fragment() {

    private var _binding: FragmentProfileBinding? = null
    private val binding get() = _binding!!

    private val viewModel: ProfileViewModel by activityViewModels()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentProfileBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupClickListeners()
        observeData()
    }

    override fun onResume() {
        super.onResume()
        viewModel.ensureLoaded()
    }

    private fun setupClickListeners() {
        binding.btnEditProfile.setOnClickListener {
            findNavController().navigate(R.id.action_profileFragment_to_editProfileFragment)
        }

        binding.cardRiskProfile.setOnClickListener {
            findNavController().navigate(R.id.action_profileFragment_to_riskProfileFragment)
        }

        binding.cardEngineWeights.setOnClickListener {
            findNavController().navigate(R.id.recommendationSettingsFragment)
        }

        binding.cardNotificationPrefs.setOnClickListener {
            findNavController().navigate(R.id.action_profileFragment_to_notificationPreferencesFragment)
        }

        binding.cardAlerts.setOnClickListener {
            findNavController().navigate(R.id.action_profileFragment_to_alertsFragment)
        }

        binding.cardNotificationsInbox.setOnClickListener {
            findNavController().navigate(R.id.action_profileFragment_to_notificationsFragment)
        }

        binding.cardCommunityProfile.setOnClickListener {
            findNavController().navigate(R.id.action_profileFragment_to_communityProfileFragment)
        }

        binding.cardCommunityNotifications.setOnClickListener {
            findNavController().navigate(R.id.action_profileFragment_to_communityNotificationsFragment)
        }

        binding.cardChangePassword.setOnClickListener {
            findNavController().navigate(R.id.action_profileFragment_to_changePasswordFragment)
        }

        binding.cardAdminModeration.setOnClickListener {
            findNavController().navigate(R.id.action_profileFragment_to_adminCommunityHub)
        }

        binding.btnLogout.setOnClickListener {
            showLogoutConfirmationDialog()
        }
    }

    private fun showLogoutConfirmationDialog() {
        MaterialAlertDialogBuilder(requireContext())
            .setTitle("Sign Out")
            .setMessage("Are you sure you want to sign out of your BASARAT account?")
            .setPositiveButton("Sign Out") { _, _ ->
                viewModel.logout()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun observeData() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                // Collect Live Profile State
                launch {
                    viewModel.profileUiState.collect { state ->
                        when (state) {
                            is ProfileUiState.Loading -> {
                                // Keep showing existing userState data if available
                            }
                            is ProfileUiState.Success -> {
                                populateProfileData(state.profile)
                            }
                            is ProfileUiState.Error -> {
                                // Silent degradation to cached user session
                            }
                        }
                    }
                }

                // Fallback / Session Cache
                launch {
                    viewModel.userState.collect { user ->
                        if (user != null && binding.tvUserName.text.isBlank()) {
                            binding.tvUserName.text = user.fullName?.takeIf { it.isNotBlank() } ?: "BASARAT Trader"
                            binding.tvUserEmail.text = user.email
                            binding.tvUserHandle.text = "@${user.username ?: "trader"}"
                        }
                    }
                }

                // Collect Logout State
                launch {
                    viewModel.logoutUiState.collect { state ->
                        when (state) {
                            is AuthUiState.Idle -> {
                                binding.pbLogout.visibility = View.GONE
                                binding.tvLogoutLabel.visibility = View.VISIBLE
                                binding.btnLogout.isEnabled = true
                            }
                            is AuthUiState.Loading -> {
                                binding.pbLogout.visibility = View.VISIBLE
                                binding.tvLogoutLabel.visibility = View.GONE
                                binding.btnLogout.isEnabled = false
                            }
                            is AuthUiState.Success -> {
                                binding.pbLogout.visibility = View.GONE
                                binding.tvLogoutLabel.visibility = View.VISIBLE
                                binding.btnLogout.isEnabled = true
                                Toast.makeText(requireContext(), "Signed out successfully", Toast.LENGTH_SHORT).show()

                                val navOptions = NavOptions.Builder()
                                    .setPopUpTo(R.id.nav_graph, true)
                                    .build()
                                findNavController().navigate(R.id.loginFragment, null, navOptions)
                                viewModel.resetLogoutState()
                            }
                            is AuthUiState.Error -> {
                                binding.pbLogout.visibility = View.GONE
                                binding.tvLogoutLabel.visibility = View.VISIBLE
                                binding.btnLogout.isEnabled = true
                                Toast.makeText(requireContext(), state.message, Toast.LENGTH_LONG).show()
                                viewModel.resetLogoutState()
                            }
                        }
                    }
                }
            }
        }
    }

    private fun populateProfileData(profile: UserProfile) {
        binding.tvUserName.text = profile.fullName?.takeIf { it.isNotBlank() } ?: "BASARAT Trader"
        binding.tvUserEmail.text = profile.email
        val verifiedBadge = if (profile.isVerified) " ✓ Verified" else ""
        binding.tvUserHandle.text = "@${profile.username}$verifiedBadge"

        // Format risk tolerance badge
        val riskText = profile.riskTolerance?.replace("_", " ")?.capitalizeWords() ?: "Not Configured"
        binding.tvBadgeRisk.text = riskText

        // Format horizon badge
        val horizonText = profile.investmentHorizon?.replace("_", " ")?.capitalizeWords() ?: "Not Set"
        binding.tvBadgeHorizon.text = horizonText

        // Update sectors summary if present
        if (profile.sectorPreferences.isNotEmpty()) {
            val count = profile.sectorPreferences.size
            val noun = if (count == 1) "sector" else "sectors"
            binding.tvRiskSummary.text = "$count preferred $noun configured"
        }
    }

    private fun String.capitalizeWords(): String = split(" ").joinToString(" ") { word ->
        word.lowercase(Locale.ROOT).replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.ROOT) else it.toString() }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
