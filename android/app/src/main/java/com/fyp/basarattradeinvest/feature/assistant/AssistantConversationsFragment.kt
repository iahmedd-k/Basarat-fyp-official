package com.fyp.basarattradeinvest.feature.assistant

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.os.bundleOf
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentAssistantConversationsBinding
import com.fyp.basarattradeinvest.feature.assistant.adapter.ConversationListAdapter
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.launch

/**
 * Screen displaying the user's past AI assistant conversations.
 * Allows creating a new chat, viewing existing chats, and deleting chats.
 */
class AssistantConversationsFragment : Fragment() {

    private var _binding: FragmentAssistantConversationsBinding? = null
    private val binding get() = _binding!!

    private val viewModel: AssistantViewModel by viewModels { AssistantViewModel.Factory() }
    private lateinit var conversationAdapter: ConversationListAdapter

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentAssistantConversationsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupToolbar()
        setupRecyclerView()
        setupListeners()
        observeState()

        viewModel.loadConversations()
    }

    override fun onResume() {
        super.onResume()
        // Refresh conversations in case a chat was opened and title was updated
        viewModel.loadConversations()
    }

    private fun setupToolbar() {
        binding.toolbar.setNavigationOnClickListener {
            findNavController().navigateUp()
        }
    }

    private fun setupRecyclerView() {
        conversationAdapter = ConversationListAdapter(
            onConversationClick = { conversation ->
                val bundle = bundleOf("conversation_id" to conversation.id)
                findNavController().navigate(
                    R.id.action_assistantConversations_to_chat,
                    bundle
                )
            },
            onDeleteClick = { conversation ->
                showDeleteConfirmationDialog(conversation.id)
            }
        )

        binding.rvConversations.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = conversationAdapter
        }
    }

    private fun setupListeners() {
        binding.fabNewConversation.setOnClickListener {
            // Navigate to chat with null conversationId to start a new chat
            findNavController().navigate(
                R.id.action_assistantConversations_to_chat,
                bundleOf("conversation_id" to null)
            )
        }

        binding.btnRetry.setOnClickListener {
            viewModel.loadConversations()
        }
    }

    private fun showDeleteConfirmationDialog(conversationId: String) {
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.delete_conversation_title)
            .setMessage(R.string.delete_conversation_message)
            .setPositiveButton(R.string.delete) { _, _ ->
                viewModel.deleteConversation(conversationId)
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.conversationListState.collect { state ->
                    renderUiState(state)
                }
            }
        }
    }

    private fun renderUiState(state: ConversationListUiState) {
        when (state) {
            is ConversationListUiState.Loading -> {
                binding.progressLoading.visibility = View.VISIBLE
                binding.layoutEmpty.visibility = View.GONE
                binding.layoutError.visibility = View.GONE
                binding.rvConversations.visibility = View.GONE
            }

            is ConversationListUiState.Empty -> {
                binding.progressLoading.visibility = View.GONE
                binding.layoutEmpty.visibility = View.VISIBLE
                binding.layoutError.visibility = View.GONE
                binding.rvConversations.visibility = View.GONE
                conversationAdapter.submitList(emptyList())
            }

            is ConversationListUiState.Error -> {
                binding.progressLoading.visibility = View.GONE
                binding.layoutEmpty.visibility = View.GONE
                binding.layoutError.visibility = View.VISIBLE
                binding.rvConversations.visibility = View.GONE
                binding.tvErrorMessage.text = state.message
            }

            is ConversationListUiState.Success -> {
                binding.progressLoading.visibility = View.GONE
                binding.layoutEmpty.visibility = View.GONE
                binding.layoutError.visibility = View.GONE
                binding.rvConversations.visibility = View.VISIBLE
                conversationAdapter.submitList(state.conversations)
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
