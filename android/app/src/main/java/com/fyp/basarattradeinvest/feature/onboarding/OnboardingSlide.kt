package com.fyp.basarattradeinvest.feature.onboarding

import androidx.annotation.DrawableRes
import androidx.annotation.StringRes

data class OnboardingSlide(
    @param:StringRes val titleRes: Int,
    @param:StringRes val subtitleRes: Int,
    @param:DrawableRes val imageRes: Int
)
