package com.fyp.basarattradeinvest.domain.usecase.community

import com.fyp.basarattradeinvest.domain.model.community.CommunityPost
import com.fyp.basarattradeinvest.domain.repository.CommunityRepository

class CreateCommunityPostUseCase(
    private val repository: CommunityRepository
) {
    suspend operator fun invoke(
        content: String,
        postType: String,
        stockSymbol: String? = null,
        imageBytes: ByteArray? = null,
        imageFileName: String? = null,
        imageMimeType: String? = null
    ): Result<CommunityPost> {
        val trimmed = content.trim()
        if (trimmed.isBlank()) {
            return Result.failure(IllegalArgumentException("Post content cannot be empty."))
        }
        if (trimmed.length > 5000) {
            return Result.failure(IllegalArgumentException("Post content exceeds 5,000 characters limit."))
        }
        val validPostType = if (postType.equals("STOCK", ignoreCase = true)) "STOCK" else "GENERAL_MARKET"
        val validStock = if (validPostType == "STOCK") {
            val sym = stockSymbol?.trim()?.uppercase()
            if (sym.isNullOrBlank()) {
                return Result.failure(IllegalArgumentException("Please specify a stock ticker for Stock Idea posts."))
            }
            sym
        } else {
            null
        }

        return repository.createPost(
            content = trimmed,
            postType = validPostType,
            stockSymbol = validStock,
            imageBytes = imageBytes,
            imageFileName = imageFileName,
            imageMimeType = imageMimeType
        )
    }
}
