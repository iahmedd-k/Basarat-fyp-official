package com.fyp.basarattradeinvest.feature.community.comments

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.data.repository.CommunityRepositoryImpl
import com.fyp.basarattradeinvest.databinding.BottomSheetCommunityCommentsBinding
import com.fyp.basarattradeinvest.domain.model.community.CommunityComment
import com.fyp.basarattradeinvest.domain.usecase.community.CreateCommunityCommentUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.GetCommunityCommentsUseCase
import com.fyp.basarattradeinvest.feature.community.adapter.CommunityCommentsAdapter
import com.google.android.material.bottomsheet.BottomSheetDialogFragment
import kotlinx.coroutines.launch

class CommunityCommentsBottomSheetDialogFragment : BottomSheetDialogFragment() {

    private var _binding: BottomSheetCommunityCommentsBinding? = null
    private val binding get() = _binding!!

    private val repository = CommunityRepositoryImpl()
    private val getCommentsUseCase = GetCommunityCommentsUseCase(repository)
    private val createCommentUseCase = CreateCommunityCommentUseCase(repository)

    private lateinit var commentsAdapter: CommunityCommentsAdapter
    private val commentsList = mutableListOf<CommunityComment>()

    var onCommentAdded: ((newTotal: Int) -> Unit)? = null

    private var postId: String = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        postId = arguments?.getString(ARG_POST_ID) ?: ""
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = BottomSheetCommunityCommentsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupRecyclerView()
        setupListeners()
        loadComments()
    }

    private fun setupRecyclerView() {
        commentsAdapter = CommunityCommentsAdapter()
        binding.rvComments.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = commentsAdapter
        }
    }

    private fun setupListeners() {
        binding.btnClose.setOnClickListener {
            dismiss()
        }

        binding.btnSendComment.setOnClickListener {
            submitComment()
        }
    }

    private fun loadComments() {
        if (postId.isBlank()) return

        binding.progressBar.visibility = View.VISIBLE
        binding.layoutEmptyComments.visibility = View.GONE

        viewLifecycleOwner.lifecycleScope.launch {
            val result = getCommentsUseCase(postId = postId)
            if (_binding == null) return@launch
            binding.progressBar.visibility = View.GONE

            if (result.isSuccess) {
                val list = result.getOrNull()?.comments ?: emptyList()
                commentsList.clear()
                commentsList.addAll(list)
                commentsAdapter.submitList(commentsList.toList())
                updateCommentCountUI(commentsList.size)
            } else {
                updateCommentCountUI(commentsList.size)
            }
        }
    }

    private fun submitComment() {
        val text = binding.etCommentInput.text?.toString()?.trim() ?: ""
        if (text.isBlank()) {
            return
        }

        binding.btnSendComment.isEnabled = false
        binding.ivSendIcon.visibility = View.GONE
        binding.progressSend.visibility = View.VISIBLE

        viewLifecycleOwner.lifecycleScope.launch {
            val result = createCommentUseCase(postId = postId, content = text)
            if (_binding == null) return@launch
            binding.btnSendComment.isEnabled = true
            binding.ivSendIcon.visibility = View.VISIBLE
            binding.progressSend.visibility = View.GONE

            if (result.isSuccess) {
                val newComment = result.getOrNull()!!
                commentsList.add(newComment)
                commentsAdapter.submitList(commentsList.toList())
                binding.etCommentInput.setText("")
                updateCommentCountUI(commentsList.size)
                binding.rvComments.scrollToPosition(commentsList.size - 1)
                onCommentAdded?.invoke(commentsList.size)
            } else {
                Toast.makeText(requireContext(), "Failed to post comment. Please try again.", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun updateCommentCountUI(count: Int) {
        binding.tvHeaderCount.text = count.toString()
        if (count == 0) {
            binding.layoutEmptyComments.visibility = View.VISIBLE
        } else {
            binding.layoutEmptyComments.visibility = View.GONE
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    companion object {
        const val TAG = "CommunityCommentsBottomSheet"
        private const val ARG_POST_ID = "arg_post_id"

        fun newInstance(postId: String): CommunityCommentsBottomSheetDialogFragment {
            return CommunityCommentsBottomSheetDialogFragment().apply {
                arguments = Bundle().apply {
                    putString(ARG_POST_ID, postId)
                }
            }
        }
    }
}
