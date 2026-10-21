package com.fyp.basarattradeinvest.feature.ipo

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.navigation.fragment.findNavController
import androidx.viewpager2.adapter.FragmentStateAdapter
import com.fyp.basarattradeinvest.databinding.FragmentIpoHostBinding
import com.google.android.material.tabs.TabLayoutMediator

/**
 * Hosts the three IPO tabs (Directory, Calendar, Performance) in a ViewPager2. Children share a
 * single [IpoViewModel] scoped to this fragment so each tab loads lazily and keeps its state when
 * the user switches tabs or returns from a detail screen.
 */
class IpoFragment : Fragment() {

    private var _binding: FragmentIpoHostBinding? = null
    private val binding get() = _binding!!

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentIpoHostBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        binding.ivBack.setOnClickListener { findNavController().popBackStack() }

        binding.viewPager.adapter = IpoPagerAdapter(this)
        binding.viewPager.offscreenPageLimit = 1

        TabLayoutMediator(binding.tabLayout, binding.viewPager) { tab, position ->
            tab.text = when (position) {
                0 -> "Directory"
                1 -> "Calendar"
                2 -> "Performance"
                else -> ""
            }
        }.attach()
    }

    override fun onDestroyView() {
        binding.viewPager.adapter = null
        super.onDestroyView()
        _binding = null
    }

    private class IpoPagerAdapter(host: Fragment) : FragmentStateAdapter(host) {
        override fun getItemCount(): Int = 3

        override fun createFragment(position: Int): Fragment = when (position) {
            1 -> IpoCalendarFragment()
            2 -> IpoPerformanceFragment()
            else -> IpoDirectoryFragment()
        }
    }
}
