package com.fyp.basarattradeinvest.feature.auth

import android.app.Activity
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import androidx.credentials.exceptions.NoCredentialException
import com.fyp.basarattradeinvest.R
import com.google.android.libraries.identity.googleid.GetGoogleIdOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential

/**
 * Shared "Continue with Google" launcher for the Sign In and Sign Up screens.
 *
 * Produces the Google OAuth ID token that POST /api/v1/auth/google expects. A success
 * holding null means the user backed out of the account picker, which is not an error.
 */
object GoogleSignInLauncher {

    suspend fun requestIdToken(activity: Activity): Result<String?> {
        val serverClientId = activity.getString(R.string.google_web_client_id).trim()
        if (serverClientId.isEmpty()) {
            return Result.failure(
                Exception("Google Sign-In is not configured in this build yet.")
            )
        }

        val googleIdOption = GetGoogleIdOption.Builder()
            .setServerClientId(serverClientId)
            .setFilterByAuthorizedAccounts(false)
            .build()
        val request = GetCredentialRequest.Builder()
            .addCredentialOption(googleIdOption)
            .build()

        return try {
            val credential = CredentialManager.create(activity).getCredential(activity, request).credential
            when {
                // Credential Manager wraps Google ID tokens in a CustomCredential; the token
                // itself is parsed out of its data bundle. Expecting GoogleIdTokenCredential
                // directly never matches and misreports every sign-in as unsupported.
                credential is CustomCredential &&
                    credential.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL ->
                    Result.success(GoogleIdTokenCredential.createFrom(credential.data).idToken)
                credential is CustomCredential -> Result.failure(
                    Exception("Google returned an unsupported credential (${credential.type}).")
                )
                else -> Result.failure(Exception("Google Sign-In did not return an ID token."))
            }
        } catch (cancelled: GetCredentialCancellationException) {
            Result.success(null)
        } catch (noCredential: NoCredentialException) {
            // Play Services also raises this when it refuses the caller outright, i.e. the app's
            // package + signing fingerprint are not registered as an OAuth client for the
            // configured ID. Blaming the device's Google accounts sends people the wrong way.
            Result.failure(
                Exception("Google does not recognise this app build — its package name and SHA-1 " +
                    "must be registered as an OAuth client for the configured client ID.")
            )
        } catch (error: GetCredentialException) {
            Result.failure(Exception(error.message ?: "Google Sign-In failed. Please try again."))
        } catch (error: Exception) {
            Result.failure(Exception("Google Sign-In failed. Please try again."))
        }
    }
}
