package com.fyp.basarattradeinvest.feature.community.create

import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.fyp.basarattradeinvest.databinding.BottomSheetCreatePostBinding
import com.google.android.material.bottomsheet.BottomSheetDialogFragment
import com.google.android.material.chip.Chip
import kotlinx.coroutines.launch

class CreatePostBottomSheetDialogFragment : BottomSheetDialogFragment() {

    private var _binding: BottomSheetCreatePostBinding? = null
    private val binding get() = _binding!!

    private val viewModel: CreatePostViewModel by viewModels {
        CreatePostViewModel.Factory()
    }

    var onPostCreated: (() -> Unit)? = null

    private var selectedImageUri: Uri? = null
    private var selectedImageBytes: ByteArray? = null
    private var selectedImageFileName: String? = null
    private var selectedImageMimeType: String? = null

    private var currentPostType: String = "STOCK"

    private val pickImageLauncher = registerForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        if (uri != null) {
            handleImagePicked(uri)
        }
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = BottomSheetCreatePostBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupTagChips()
        setupQuickStockChips()
        setupListeners()
        observeUiState()
    }

    private fun setupTagChips() {
        binding.chipGroupTag.setOnCheckedStateChangeListener { _, checkedIds ->
            if (checkedIds.contains(binding.chipTagGeneral.id)) {
                currentPostType = "GENERAL_MARKET"
                binding.layoutStockSelection.visibility = View.GONE
            } else {
                currentPostType = "STOCK"
                binding.layoutStockSelection.visibility = View.VISIBLE
            }
        }
    }

    private fun setupQuickStockChips() {
        binding.chipGroupQuickStocks.setOnCheckedStateChangeListener { group, checkedIds ->
            if (checkedIds.isNotEmpty()) {
                val selectedChip = group.findViewById<Chip>(checkedIds.first())
                if (selectedChip != null) {
                    binding.etStockSymbol.setText(selectedChip.text.toString().trim())
                }
            }
        }
    }

    private fun setupListeners() {
        binding.btnClose.setOnClickListener {
            dismiss()
        }

        binding.btnAttachImage.setOnClickListener {
            pickImageLauncher.launch("image/*")
        }

        binding.btnRemoveImage.setOnClickListener {
            clearSelectedImage()
        }

        binding.btnSharePost.setOnClickListener {
            validateAndSubmit()
        }
    }

    private fun handleImagePicked(uri: Uri) {
        selectedImageUri = uri
        try {
            val contentResolver = requireContext().contentResolver
            contentResolver.openInputStream(uri)?.use { inputStream ->
                selectedImageBytes = inputStream.readBytes()
            }
            val mime = contentResolver.getType(uri) ?: "image/jpeg"
            selectedImageMimeType = mime
            val ext = if (mime.contains("png")) "png" else "jpg"
            selectedImageFileName = "basarat_post_${System.currentTimeMillis()}.$ext"

            binding.ivPreviewImage.setImageURI(uri)
            binding.cardImagePreview.visibility = View.VISIBLE
            binding.tvImageStatus.text = "1 image attached"
        } catch (e: Exception) {
            Toast.makeText(requireContext(), "Failed to read image: ${e.localizedMessage}", Toast.LENGTH_SHORT).show()
            clearSelectedImage()
        }
    }

    private fun clearSelectedImage() {
        selectedImageUri = null
        selectedImageBytes = null
        selectedImageFileName = null
        selectedImageMimeType = null
        binding.ivPreviewImage.setImageURI(null)
        binding.cardImagePreview.visibility = View.GONE
        binding.tvImageStatus.text = ""
    }

    private fun validateAndSubmit() {
        val content = binding.etContent.text?.toString()?.trim().orEmpty()
        if (content.isBlank()) {
            showError("Please enter your post content.")
            binding.etContent.requestFocus()
            return
        }

        val stockSymbol = if (currentPostType == "STOCK") {
            val sym = binding.etStockSymbol.text?.toString()?.trim()?.uppercase().orEmpty()
            if (sym.isBlank()) {
                showError("Please specify a stock ticker for Stock Idea.")
                binding.etStockSymbol.requestFocus()
                return
            }
            sym
        } else {
            null
        }

        hideError()
        viewModel.submitPost(
            content = content,
            postType = currentPostType,
            stockSymbol = stockSymbol,
            imageBytes = selectedImageBytes,
            imageFileName = selectedImageFileName,
            imageMimeType = selectedImageMimeType
        )
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is CreatePostUiState.Idle -> {
                            setSubmitting(false)
                            hideError()
                        }
                        is CreatePostUiState.Submitting -> {
                            setSubmitting(true)
                            hideError()
                        }
                        is CreatePostUiState.Success -> {
                            setSubmitting(false)
                            Toast.makeText(requireContext(), "Post shared successfully to Community!", Toast.LENGTH_LONG).show()
                            onPostCreated?.invoke()
                            dismiss()
                        }
                        is CreatePostUiState.Error -> {
                            setSubmitting(false)
                            showError(state.message)
                        }
                    }
                }
            }
        }
    }

    private fun setSubmitting(isSubmitting: Boolean) {
        binding.btnSharePost.isEnabled = !isSubmitting
        binding.btnSharePost.text = if (isSubmitting) "" else "Share Post"
        binding.progressSubmitting.visibility = if (isSubmitting) View.VISIBLE else View.GONE
        binding.btnAttachImage.isEnabled = !isSubmitting
        binding.btnRemoveImage.isEnabled = !isSubmitting
        binding.etContent.isEnabled = !isSubmitting
        binding.etStockSymbol.isEnabled = !isSubmitting
    }

    private fun showError(message: String) {
        binding.tvErrorMessage.text = message
        binding.tvErrorMessage.visibility = View.VISIBLE
    }

    private fun hideError() {
        binding.tvErrorMessage.visibility = View.GONE
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    companion object {
        const val TAG = "CreatePostBottomSheet"

        fun newInstance(): CreatePostBottomSheetDialogFragment {
            return CreatePostBottomSheetDialogFragment()
        }
    }
}
