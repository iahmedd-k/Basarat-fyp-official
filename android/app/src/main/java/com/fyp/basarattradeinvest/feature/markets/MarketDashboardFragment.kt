package com.fyp.basarattradeinvest.feature.markets

import android.content.res.ColorStateList
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.core.notifications.NotificationBadgeState
import com.fyp.basarattradeinvest.databinding.FragmentMarketDashboardBinding
import com.fyp.basarattradeinvest.domain.model.market.MarketIndex
import com.fyp.basarattradeinvest.domain.model.live.MarketSessionStatus
import com.fyp.basarattradeinvest.domain.model.live.WsConnectionState
import com.fyp.basarattradeinvest.feature.markets.adapter.MarketStockAdapter
import com.fyp.basarattradeinvest.feature.markets.adapter.SectorPerformanceAdapter
import kotlinx.coroutines.launch
import java.util.Locale

class MarketDashboardFragment : Fragment() {

    private var _binding: FragmentMarketDashboardBinding? = null
    private val binding get() = _binding!!

    private val viewModel: MarketDashboardViewModel by activityViewModels()

    private var lastRenderedSuccess: MarketDashboardUiState.Success? = null

    private val stockAdapter = MarketStockAdapter { stock ->
        val bundle = Bundle().apply { putString("symbol", stock.symbol) }
        findNavController().navigate(R.id.stockDetailFragment, bundle)
    }

    private val sectorAdapter = SectorPerformanceAdapter { sector ->
        Toast.makeText(requireContext(), "${sector.sectorName}: ${sector.changePercent}%", Toast.LENGTH_SHORT).show()
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentMarketDashboardBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupRecyclerViews()
        setupSwipeRefresh()
        setupTabListeners()
        setupTopBarListeners()
        observeUiState()
        observeNotificationBadge()
        viewModel.ensureLoaded()
    }

    private fun setupRecyclerViews() {
        binding.rvTopSymbols.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = stockAdapter
        }

        binding.rvSectors.apply {
            layoutManager = LinearLayoutManager(requireContext(), LinearLayoutManager.HORIZONTAL, false)
            adapter = sectorAdapter
        }
    }

    private fun setupSwipeRefresh() {
        binding.swipeRefreshLayout.setColorSchemeResources(R.color.color_basarat_green)
        binding.swipeRefreshLayout.setOnRefreshListener {
            viewModel.refreshData()
        }
    }

    private fun setupTabListeners() {
        binding.tabKse100.setOnClickListener { viewModel.setSelection(MarketListSelection.KSE_100) }
        binding.tabKse30.setOnClickListener { viewModel.setSelection(MarketListSelection.KSE_30) }
        binding.tabKmi30.setOnClickListener { viewModel.setSelection(MarketListSelection.KMI_30) }
        binding.tabGainers.setOnClickListener { viewModel.setSelection(MarketListSelection.GAINERS) }
        binding.tabLosers.setOnClickListener { viewModel.setSelection(MarketListSelection.LOSERS) }
        binding.tabVolumeSpikes.setOnClickListener { viewModel.setSelection(MarketListSelection.VOLUME_SPIKES) }
        binding.tabMostActive.setOnClickListener { viewModel.setSelection(MarketListSelection.MOST_ACTIVE) }

        binding.ivQuoteBannerClose.setOnClickListener {
            binding.bannerRealtimeQuotes.visibility = View.GONE
        }
    }

    private fun setupTopBarListeners() {
        binding.ivTopMenu.setOnClickListener {
            Toast.makeText(requireContext(), "Menu drawer", Toast.LENGTH_SHORT).show()
        }
        binding.ivTopNotifications.setOnClickListener {
            findNavController().navigate(R.id.notificationsFragment)
        }
        binding.ivTopSearch.setOnClickListener {
            findNavController().navigate(R.id.stockSearchFragment)
        }
        binding.tvSectorsSeeAll.setOnClickListener {
            Toast.makeText(requireContext(), "Sector Heatmap", Toast.LENGTH_SHORT).show()
        }
        binding.chipShariah.setOnClickListener {
            findNavController().navigate(R.id.shariahScreeningFragment)
        }
        binding.layoutIndex2.setOnClickListener {
            findNavController().navigate(R.id.shariahScreeningFragment)
        }
        binding.chipCommunity.setOnClickListener {
            findNavController().navigate(R.id.communityProfileFragment)
        }
        binding.chipNews.setOnClickListener {
            findNavController().navigate(R.id.newsEventsFragment)
        }
        binding.chipRecommendations.setOnClickListener {
            findNavController().navigate(R.id.recommendationsFragment)
        }
        binding.chipSmartSelection.setOnClickListener {
            findNavController().navigate(R.id.smart_selection_fragment)
        }
        binding.chipIpo.setOnClickListener {
            findNavController().navigate(R.id.ipoFragment)
        }
        binding.chipEtf.setOnClickListener {
            findNavController().navigate(R.id.etfDirectoryFragment)
        }

        binding.fabChatAssistant.setOnClickListener {
            findNavController().navigate(R.id.assistantChatFragment)
        }
    }

    private fun observeNotificationBadge() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                NotificationBadgeState.unreadCount.collect { unreadCount ->
                    binding.tvNotificationsBadge.visibility = if (unreadCount > 0) View.VISIBLE else View.GONE
                    binding.tvNotificationsBadge.text = if (unreadCount > 99) "99+" else unreadCount.toString()
                }
            }
        }
    }

    override fun onStart() {
        super.onStart()
        viewModel.setLiveUpdatesActive(true)
    }

    override fun onStop() {
        viewModel.setLiveUpdatesActive(false)
        super.onStop()
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is MarketDashboardUiState.Loading -> {
                            // Non-blocking loading
                        }
                        is MarketDashboardUiState.Success -> {
                            binding.swipeRefreshLayout.isRefreshing = false
                            val previous = lastRenderedSuccess
                            if (previous?.lastUpdated != state.lastUpdated) {
                                binding.tvLastUpdated.text = "• Updated ${state.lastUpdated}"
                            }
                            val dataIsStale = state.liveQuotes.values.any { it.isStale }
                            if (previous == null || previous.wsConnectionState != state.wsConnectionState ||
                                previous.liveQuotes.values.any { it.isStale } != dataIsStale
                            ) {
                                bindLiveConnection(state, dataIsStale)
                            }
                            if (previous == null || previous.marketSession != state.marketSession) {
                                bindMarketSession(state.marketSession)
                            }
                            if (previous == null || previous.indices != state.indices) {
                                bindIndices(state.indices)
                            }
                            if (previous == null || previous.sectors != state.sectors) {
                                sectorAdapter.submitList(state.sectors.toList())
                            }
                            if (previous == null || previous.selection != state.selection) {
                                binding.tvTopSymbolsHeader.text = state.selection.headerTitle
                                bindSelectorTabs(state.selection)
                            }
                            if (previous == null || previous.rows != state.rows ||
                                previous.isRowsLoading != state.isRowsLoading
                            ) {
                                bindRows(state)
                            }
                            lastRenderedSuccess = state
                        }
                        is MarketDashboardUiState.Empty -> {
                            binding.swipeRefreshLayout.isRefreshing = false
                            lastRenderedSuccess = null
                            bindMarketSession(null)
                            stockAdapter.submitList(emptyList())
                        }
                        is MarketDashboardUiState.Error -> {
                            binding.swipeRefreshLayout.isRefreshing = false
                            lastRenderedSuccess = null
                            bindMarketSession(null)
                            Toast.makeText(requireContext(), state.message, Toast.LENGTH_SHORT).show()
                        }
                    }
                }
            }
        }
    }

    private fun bindMarketSession(session: MarketSessionStatus?) {
        binding.dotMarketLive.visibility = if (session == null) View.GONE else View.VISIBLE
        binding.tvMarketStatus.visibility = if (session == null) View.GONE else View.VISIBLE
        if (session == null) return
        val color = ContextCompat.getColor(
            requireContext(),
            if (session.isOpen) R.color.color_positive else R.color.color_neutral
        )
        binding.tvMarketStatus.text = session.label
        binding.tvMarketStatus.setTextColor(color)
        binding.dotMarketLive.backgroundTintList = ColorStateList.valueOf(color)
    }

    private fun bindLiveConnection(state: MarketDashboardUiState.Success, dataIsStale: Boolean) {
        if (dataIsStale) {
            binding.tvQuoteBannerText.text = "Market data delayed"
            return
        }
        binding.tvQuoteBannerText.text = when (val connection = state.wsConnectionState) {
            WsConnectionState.Live -> "Live PSX quote stream connected"
            is WsConnectionState.Connecting -> "Connecting to live PSX quotes"
            is WsConnectionState.Reconnecting -> "Reconnecting to live PSX quotes"
            is WsConnectionState.Delayed -> "Live quotes reconnecting · ${connection.nextRetryInSeconds}s"
            WsConnectionState.Idle, WsConnectionState.Closed -> "Live PSX quotes disconnected"
        }
    }

    private fun bindIndices(indices: List<MarketIndex>) {
        if (indices.isEmpty()) return

        val kse100 = indices.firstOrNull {
            it.name.contains("100", ignoreCase = true) || it.code.contains("100", ignoreCase = true)
        } ?: indices.getOrNull(0)

        val kse30 = indices.firstOrNull {
            (it.name.contains("KSE-30", ignoreCase = true) || it.code.contains("KSE30", ignoreCase = true)) &&
                !it.name.contains("KMI", ignoreCase = true)
        } ?: indices.getOrNull(1)

        val kmi30 = indices.firstOrNull {
            it.name.contains("KMI", ignoreCase = true) || it.code.contains("KMI", ignoreCase = true)
        } ?: indices.getOrNull(2)

        // 1. KSE-100
        kse100?.let { idx ->
            binding.tvIndex1Name.text = idx.name
            binding.tvIndex1Points.text = String.format(Locale.US, "%,.2f", idx.currentPoints)
            val prefix = if (idx.changePercent >= 0) "+" else ""
            binding.tvIndex1Change.text = String.format(Locale.US, "%.2f  %s%.2f%%", idx.changePoints, prefix, idx.changePercent)
            val color = if (idx.changePercent >= 0) R.color.color_positive else R.color.color_negative
            binding.tvIndex1Change.setTextColor(ContextCompat.getColor(requireContext(), color))
        }

        // 2. KSE-30
        kse30?.let { idx ->
            binding.tvIndex3Name.text = idx.name
            binding.tvIndex3Points.text = String.format(Locale.US, "%,.2f", idx.currentPoints)
            val prefix = if (idx.changePercent >= 0) "+" else ""
            binding.tvIndex3Change.text = String.format(Locale.US, "%.2f  %s%.2f%%", idx.changePoints, prefix, idx.changePercent)
            val color = if (idx.changePercent >= 0) R.color.color_positive else R.color.color_negative
            binding.tvIndex3Change.setTextColor(ContextCompat.getColor(requireContext(), color))
        }

        // 3. KMI-30
        kmi30?.let { idx ->
            binding.tvIndex2Name.text = idx.name
            binding.tvIndex2Points.text = String.format(Locale.US, "%,.2f", idx.currentPoints)
            val prefix = if (idx.changePercent >= 0) "+" else ""
            binding.tvIndex2Change.text = String.format(Locale.US, "%.2f  %s%.2f%%", idx.changePoints, prefix, idx.changePercent)
            val color = if (idx.changePercent >= 0) R.color.color_positive else R.color.color_negative
            binding.tvIndex2Change.setTextColor(ContextCompat.getColor(requireContext(), color))
        }

        // Chart Intraday
        val idx1Points = kse100?.intradayPoints ?: emptyList()
        val idx2Points = kmi30?.intradayPoints ?: emptyList()
        if (idx1Points.isNotEmpty() || idx2Points.isNotEmpty()) {
            binding.chartIntraday.setChartData(idx1Points, idx2Points)
        }
    }

    private fun bindSelectorTabs(selected: MarketListSelection) {
        val tabs = listOf(
            binding.tabKse100 to MarketListSelection.KSE_100,
            binding.tabKse30 to MarketListSelection.KSE_30,
            binding.tabKmi30 to MarketListSelection.KMI_30,
            binding.tabGainers to MarketListSelection.GAINERS,
            binding.tabLosers to MarketListSelection.LOSERS,
            binding.tabVolumeSpikes to MarketListSelection.VOLUME_SPIKES,
            binding.tabMostActive to MarketListSelection.MOST_ACTIVE
        )

        val selectedBg = R.drawable.bg_market_tab_selected
        val unselectedBg = R.drawable.bg_market_tab_unselected
        val selectedTextColor = ContextCompat.getColor(requireContext(), R.color.white)
        val unselectedTextColor = ContextCompat.getColor(requireContext(), R.color.color_text_primary)

        tabs.forEach { (tabView, selection) ->
            if (selection == selected) {
                tabView.setBackgroundResource(selectedBg)
                tabView.setTextColor(selectedTextColor)
            } else {
                tabView.setBackgroundResource(unselectedBg)
                tabView.setTextColor(unselectedTextColor)
            }
        }
    }

    private fun bindRows(state: MarketDashboardUiState.Success) {
        binding.layoutSymbolsSkeleton.visibility =
            if (state.isRowsLoading && state.rows.isEmpty()) View.VISIBLE else View.GONE
        binding.rvTopSymbols.visibility =
            if (state.isRowsLoading && state.rows.isEmpty()) View.GONE else View.VISIBLE
        binding.tvTopSymbolsCount.text = if (state.rows.isEmpty()) {
            ""
        } else {
            "${state.rows.size} symbols"
        }
        stockAdapter.submitList(state.rows.toList())
    }

    override fun onDestroyView() {
        super.onDestroyView()
        lastRenderedSuccess = null
        _binding = null
    }
}
