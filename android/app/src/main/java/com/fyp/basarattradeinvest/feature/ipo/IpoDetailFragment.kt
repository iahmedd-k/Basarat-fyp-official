package com.fyp.basarattradeinvest.feature.ipo

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
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
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentIpoDetailBinding
import com.fyp.basarattradeinvest.databinding.ItemDetailLabelValueBinding
import com.fyp.basarattradeinvest.domain.model.ipo.IpoItem
import com.fyp.basarattradeinvest.feature.common.FormatUtils
import kotlinx.coroutines.launch
import java.util.Locale

class IpoDetailFragment : Fragment() {

    private var _binding: FragmentIpoDetailBinding? = null
    private val binding get() = _binding!!

    private val viewModel: IpoDetailViewModel by activityViewModels()

    private var symbol: String = ""

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentIpoDetailBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        symbol = arguments?.getString("symbol").orEmpty()

        binding.ivBack.setOnClickListener { findNavController().popBackStack() }
        binding.btnRetry.setOnClickListener { viewModel.load(symbol) }

        observeState()
        viewModel.ensureLoaded(symbol)
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is IpoDetailUiState.Loading -> {
                            binding.layoutSkeleton.visibility = View.VISIBLE
                            binding.scrollContent.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                        }

                        is IpoDetailUiState.Success -> {
                            binding.layoutSkeleton.visibility = View.GONE
                            binding.scrollContent.visibility = View.VISIBLE
                            binding.layoutError.visibility = View.GONE
                            render(state.ipo)
                        }

                        is IpoDetailUiState.Error -> {
                            binding.layoutSkeleton.visibility = View.GONE
                            binding.scrollContent.visibility = View.GONE
                            binding.layoutError.visibility = View.VISIBLE
                            binding.tvErrorMessage.text = state.message
                        }
                    }
                }
            }
        }
    }

    private fun render(ipo: IpoItem) {
        binding.tvTopTitle.text = if (ipo.symbol.isNotBlank()) ipo.symbol else "IPO Detail"
        binding.tvIpoCompany.text = ipo.companyName
        binding.tvIpoSymbol.text = ipo.symbol

        // Status badge
        binding.tvIpoStatus.text = FormatUtils.ipoStatus(ipo.status)
        val (badgeBg, badgeColor) = when (ipo.status) {
            "OPEN_FOR_BOOK_BUILDING", "OPEN_FOR_PUBLIC_SUBSCRIPTION" ->
                R.drawable.bg_badge_positive to R.color.color_positive
            "LISTED" -> R.drawable.bg_badge_teal to R.color.color_shariah_teal
            else -> R.drawable.bg_badge_neutral to R.color.color_neutral
        }
        binding.tvIpoStatus.setBackgroundResource(badgeBg)
        binding.tvIpoStatus.setTextColor(ContextCompat.getColor(requireContext(), badgeColor))

        binding.tvIpoShariah.visibility =
            if (ipo.isShariahCompliant) View.VISIBLE else View.GONE

        if (ipo.sector.isNullOrBlank()) {
            binding.tvIpoSector.visibility = View.GONE
        } else {
            binding.tvIpoSector.visibility = View.VISIBLE
            binding.tvIpoSector.text = ipo.sector
        }

        // Pricing
        setRow(binding.rowFloorPrice, "Floor Price", FormatUtils.pricePk(ipo.floorPrice))
        setRow(binding.rowStrikePrice, "Strike Price", FormatUtils.pricePk(ipo.strikePrice))
        setRow(binding.rowListingPrice, "Listing Price", FormatUtils.pricePk(ipo.listingPrice))
        setRow(binding.rowCurrentPrice, "Current Price", FormatUtils.pricePk(ipo.currentPrice))
        setRow(binding.rowIssueSize, "Issue Size", issueSizeLabel(ipo))

        // Performance — hide the whole section when neither gain is available
        if (ipo.listingGainPct == null && ipo.currentGainPct == null) {
            binding.titlePerformance.visibility = View.GONE
            binding.layoutPerformance.visibility = View.GONE
        } else {
            binding.titlePerformance.visibility = View.VISIBLE
            binding.layoutPerformance.visibility = View.VISIBLE
            setRow(binding.rowListingGain, "Listing-day Gain", FormatUtils.percentSigned(ipo.listingGainPct))
            setRow(binding.rowCurrentGain, "Current Gain", FormatUtils.percentSigned(ipo.currentGainPct))
        }

        // Key dates
        setRow(binding.rowBookBuilding, "Book Building", dateRange(ipo.bookBuildingStart, ipo.bookBuildingEnd))
        setRow(binding.rowSubscription, "Public Subscription", dateRange(ipo.publicSubscriptionStart, ipo.publicSubscriptionEnd))
        setRow(binding.rowListingDate, "Listing Date", ipo.listingDate?.let { FormatUtils.dateFull(it) })

        // Offering
        setRow(binding.rowLeadManager, "Lead Manager", ipo.leadManager)
        setRow(
            binding.rowSubscriptionMultiplier,
            "Subscription Multiplier",
            ipo.subscriptionMultiplier?.let { String.format(Locale.US, "%.2fx", it) }
        )

        // About
        if (ipo.description.isNullOrBlank()) {
            binding.titleAbout.visibility = View.GONE
            binding.tvIpoDescription.visibility = View.GONE
        } else {
            binding.titleAbout.visibility = View.VISIBLE
            binding.tvIpoDescription.visibility = View.VISIBLE
            binding.tvIpoDescription.text = ipo.description
        }

        // Prospectus
        if (ipo.prospectusUrl.isNullOrBlank()) {
            binding.btnProspectus.visibility = View.GONE
        } else {
            binding.btnProspectus.visibility = View.VISIBLE
            binding.btnProspectus.setOnClickListener { openProspectus(ipo.prospectusUrl) }
        }
    }

    private fun setRow(row: ItemDetailLabelValueBinding, label: String, value: String?) {
        if (value.isNullOrBlank() || value == FormatUtils.NA) {
            row.root.visibility = View.GONE
        } else {
            row.root.visibility = View.VISIBLE
            row.tvLabel.text = label
            row.tvValue.text = value
        }
    }

    private fun issueSizeLabel(ipo: IpoItem): String? = when {
        ipo.issueSizePkr != null -> FormatUtils.largeAmountPkr(ipo.issueSizePkr)
        ipo.issueSizeShares != null ->
            String.format(Locale.US, "%,d shares", ipo.issueSizeShares)
        else -> null
    }

    private fun dateRange(start: String?, end: String?): String? {
        val s = FormatUtils.parseDate(start)
        val e = FormatUtils.parseDate(end)
        return when {
            s != null && e != null -> "${FormatUtils.dateFull(start)} – ${FormatUtils.dateFull(end)}"
            s != null -> FormatUtils.dateFull(start)
            e != null -> FormatUtils.dateFull(end)
            else -> null
        }
    }

    private fun openProspectus(url: String) {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
        try {
            startActivity(intent)
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(requireContext(), "No browser available to open the prospectus.", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
