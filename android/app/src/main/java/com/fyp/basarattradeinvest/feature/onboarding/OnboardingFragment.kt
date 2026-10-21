package com.fyp.basarattradeinvest.feature.onboarding

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.navigation.fragment.findNavController
import androidx.viewpager2.widget.ViewPager2
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentOnboardingBinding

class OnboardingFragment : Fragment() {

    private var _binding: FragmentOnboardingBinding? = null
    private val binding get() = _binding!!

    private val slides = listOf(
        OnboardingSlide(
            titleRes = R.string.onboarding_title_1,
            subtitleRes = R.string.onboarding_subtitle_1,
            imageRes = R.drawable.ic_onboarding_step1
        ),
        OnboardingSlide(
            titleRes = R.string.onboarding_title_2,
            subtitleRes = R.string.onboarding_subtitle_2,
            imageRes = R.drawable.ic_onboarding_step2
        ),
        OnboardingSlide(
            titleRes = R.string.onboarding_title_3,
            subtitleRes = R.string.onboarding_subtitle_3,
            imageRes = R.drawable.ic_onboarding_step3
        )
    )

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentOnboardingBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupViewPager()
        setupClickListeners()
    }

    private fun setupViewPager() {
        binding.viewPager.adapter = OnboardingAdapter(slides)
        binding.viewPager.registerOnPageChangeCallback(object : ViewPager2.OnPageChangeCallback() {
            override fun onPageSelected(position: Int) {
                super.onPageSelected(position)
                updateUiForPage(position)
            }
        })
        updateUiForPage(0)
    }

    private fun updateUiForPage(position: Int) {
        val isLastPage = position == slides.size - 1

        // Update indicators
        binding.ivDot1.setImageResource(if (position == 0) R.drawable.indicator_dot_active else R.drawable.indicator_dot_inactive)
        binding.ivDot2.setImageResource(if (position == 1) R.drawable.indicator_dot_active else R.drawable.indicator_dot_inactive)
        binding.ivDot3.setImageResource(if (position == 2) R.drawable.indicator_dot_active else R.drawable.indicator_dot_inactive)

        // Update Skip button & Action label
        if (isLastPage) {
            binding.tvSkip.visibility = View.INVISIBLE
            binding.tvActionLabel.setText(R.string.onboarding_get_started)
        } else {
            binding.tvSkip.visibility = View.VISIBLE
            binding.tvActionLabel.setText(R.string.onboarding_next)
        }
    }

    private fun setupClickListeners() {
        binding.tvSkip.setOnClickListener {
            navigateToLogin()
        }

        binding.btnAction.setOnClickListener {
            val current = binding.viewPager.currentItem
            if (current < slides.size - 1) {
                binding.viewPager.setCurrentItem(current + 1, true)
            } else {
                navigateToLogin()
            }
        }
    }

    private fun navigateToLogin() {
        findNavController().navigate(R.id.action_onboardingFragment_to_loginFragment)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
