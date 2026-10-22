package com.fyp.basarattradeinvest.feature.assistant

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.EditorInfo
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.core.session.SessionManager
import com.fyp.basarattradeinvest.databinding.FragmentAssistantChatBinding
import com.fyp.basarattradeinvest.feature.assistant.adapter.ChatMessageAdapter
import com.google.android.material.snackbar.Snackbar
import kotlinx.coroutines.launch

/**
 * Chat interface screen for the BASARAT AI Investment Assistant.
 * Supports streaming responses, conversation history, regeneration, and portfolio-aware queries.
 */
class AssistantChatFragment : Fragment() {

    private var _binding: FragmentAssistantChatBinding? = null
    private val binding get() = _binding!!

    private val viewModel: AssistantViewModel by viewModels { AssistantViewModel.Factory() }
    private lateinit var chatAdapter: ChatMessageAdapter

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentAssistantChatBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val conversationId = arguments?.getString("conversation_id")

        setupHeader()
        setupRecyclerView()
        setupInput()
        observeState()

        if (!conversationId.isNullOrEmpty()) {
            viewModel.loadConversation(conversationId)
        } else {
            viewModel.startNewChat()
        }
    }

    private fun setupHeader() {
        val name = SessionManager.getCurrentUserName()
            ?.trim()
            ?.takeIf { it.isNotEmpty() }
            ?: getString(R.string.assistant_default_user)
        binding.tvAssistantGreeting.text = getString(R.string.assistant_greeting, name)

        binding.btnConversationHistory.setOnClickListener {
            findNavController().navigate(R.id.assistantConversationsFragment)
        }
    }

    private lateinit var layoutManager: LinearLayoutManager

    private fun setupRecyclerView() {
        chatAdapter = ChatMessageAdapter()
        layoutManager = LinearLayoutManager(requireContext()).apply {
            stackFromEnd = true
        }

        binding.rvMessages.apply {
            this.layoutManager = this@AssistantChatFragment.layoutManager
            adapter = chatAdapter
        }
    }

    private fun setupInput() {
        binding.btnSend.setOnClickListener {
            sendMessage()
        }

        binding.btnStopGenerating.setOnClickListener {
            viewModel.stopGenerating()
        }

        binding.etMessage.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                sendMessage()
                true
            } else {
                false
            }
        }

        binding.btnRegenerate.setOnClickListener {
            viewModel.regenerateLastResponse()
        }

        binding.btnRetry.setOnClickListener {
            val conversationId = arguments?.getString("conversation_id")
            if (!conversationId.isNullOrEmpty()) {
                viewModel.loadConversation(conversationId)
            } else {
                viewModel.startNewChat()
            }
        }
    }

    private fun sendMessage() {
        val text = binding.etMessage.text?.toString()?.trim().orEmpty()
        if (text.isNotEmpty()) {
            binding.etMessage.text?.clear()
            viewModel.sendMessage(text)
        }
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.chatState.collect { state ->
                    renderUiState(state)
                }
            }
        }
    }

    private fun renderUiState(state: ChatUiState) {
        when (state) {
            is ChatUiState.Loading -> {
                binding.progressLoading.visibility = View.VISIBLE
                binding.layoutError.visibility = View.GONE
                binding.layoutWelcome.visibility = View.GONE
                binding.rvMessages.visibility = View.GONE
                binding.btnStopGenerating.visibility = View.GONE
                binding.btnRegenerate.visibility = View.GONE
            }

            is ChatUiState.Error -> {
                binding.progressLoading.visibility = View.GONE
                binding.layoutError.visibility = View.VISIBLE
                binding.layoutWelcome.visibility = View.GONE
                binding.rvMessages.visibility = View.GONE
                binding.btnStopGenerating.visibility = View.GONE
                binding.btnRegenerate.visibility = View.GONE
                binding.tvErrorMessage.text = state.message
            }

            is ChatUiState.Active -> {
                binding.progressLoading.visibility = View.GONE
                binding.layoutError.visibility = View.GONE

                // Show welcome banner if no messages
                val hasMessages = state.messages.isNotEmpty()

                if (!hasMessages) {
                    binding.layoutWelcome.visibility = View.VISIBLE
                    binding.rvMessages.visibility = View.GONE
                } else {
                    binding.layoutWelcome.visibility = View.GONE
                    binding.rvMessages.visibility = View.VISIBLE

                    // Smart auto-scroll: only follow new chunks if user is already near the bottom
                    val lastVisiblePos = layoutManager.findLastVisibleItemPosition()
                    val totalCount = chatAdapter.itemCount
                    val isNearBottom = totalCount <= 1 || lastVisiblePos >= totalCount - 2

                    chatAdapter.submitList(state.messages) {
                        if (isNearBottom && state.messages.isNotEmpty()) {
                            binding.rvMessages.scrollToPosition(state.messages.size - 1)
                        }
                    }
                }

                // Streaming & Regenerate controls
                val isStreaming = state.isStreaming
                binding.btnStopGenerating.visibility = if (isStreaming) View.VISIBLE else View.GONE

                val canRegenerate = !state.isSending && !isStreaming && !state.isRegenerating && state.messages.any { !it.isUser }
                binding.btnRegenerate.visibility = if (canRegenerate) View.VISIBLE else View.GONE

                // Composer state
                val isBusy = state.isSending || state.isStreaming || state.isRegenerating
                binding.btnSend.isEnabled = !isBusy
                binding.btnSend.alpha = if (isBusy) 0.5f else 1.0f

                // Transient error notification
                state.errorMessage?.let { error ->
                    Snackbar.make(binding.root, error, Snackbar.LENGTH_LONG)
                        .setAction("Dismiss") { viewModel.dismissError() }
                        .show()
                }
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
