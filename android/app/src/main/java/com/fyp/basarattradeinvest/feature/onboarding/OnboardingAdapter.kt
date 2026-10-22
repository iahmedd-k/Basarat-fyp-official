package com.fyp.basarattradeinvest.feature.onboarding

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.databinding.ItemOnboardingSlideBinding

class OnboardingAdapter(
    private val slides: List<OnboardingSlide>
) : RecyclerView.Adapter<OnboardingAdapter.SlideViewHolder>() {

    inner class SlideViewHolder(
        private val binding: ItemOnboardingSlideBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(slide: OnboardingSlide) {
            binding.tvSlideTitle.setText(slide.titleRes)
            binding.tvSlideSubtitle.setText(slide.subtitleRes)
            binding.ivSlideImage.setImageResource(slide.imageRes)
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): SlideViewHolder {
        val binding = ItemOnboardingSlideBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return SlideViewHolder(binding)
    }

    override fun onBindViewHolder(holder: SlideViewHolder, position: Int) {
        holder.bind(slides[position])
    }

    override fun getItemCount(): Int = slides.size
}
