package com.fyp.basarattradeinvest.core.session

import android.content.Context
import android.content.SharedPreferences
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class SecureTokenStorage(context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    companion object {
        private const val PREFS_NAME = "basarat_secure_session_prefs"
        private const val KEY_ALIAS = "BasaratKeyAlias"
        private const val ANDROID_KEYSTORE = "AndroidKeyStore"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
        private const val GCM_IV_LENGTH = 12
        private const val GCM_TAG_LENGTH = 128

        private const val KEY_ACCESS_TOKEN = "enc_access_token"
        private const val KEY_REFRESH_TOKEN = "enc_refresh_token"
        private const val KEY_USER_ID = "user_id"
        private const val KEY_USER_EMAIL = "user_email"
        private const val KEY_USER_NAME = "user_name"
        private const val KEY_DEVICE_ID = "push_device_id"
        private const val KEY_REGISTERED_FCM_TOKEN = "registered_fcm_token"
        private const val KEY_PENDING_FCM_TOKEN = "pending_fcm_token"
        private const val KEY_NOTIFICATION_PERMISSION_ASKED = "notification_permission_asked"
    }

    init {
        try {
            ensureKeyStoreKeyExists()
        } catch (_: Exception) {
            // KeyStore may not be available in headless JVM unit tests
        }
    }

    private fun ensureKeyStoreKeyExists() {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        if (!keyStore.containsAlias(KEY_ALIAS)) {
            val keyGenerator =
                KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
            val parameterSpec = KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
            keyGenerator.init(parameterSpec)
            keyGenerator.generateKey()
        }
    }

    private fun getSecretKey(): SecretKey? {
        return try {
            val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
            val entry = keyStore.getEntry(KEY_ALIAS, null) as? KeyStore.SecretKeyEntry
            entry?.secretKey
        } catch (_: Exception) {
            null
        }
    }

    private fun encrypt(plainText: String): String {
        val secretKey = getSecretKey() ?: return Base64.encodeToString(plainText.toByteArray(Charsets.UTF_8), Base64.NO_WRAP)
        return try {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.ENCRYPT_MODE, secretKey)
            val iv = cipher.iv
            val cipherText = cipher.doFinal(plainText.toByteArray(Charsets.UTF_8))
            val combined = ByteArray(iv.size + cipherText.size)
            System.arraycopy(iv, 0, combined, 0, iv.size)
            System.arraycopy(cipherText, 0, combined, iv.size, cipherText.size)
            Base64.encodeToString(combined, Base64.NO_WRAP)
        } catch (_: Exception) {
            plainText
        }
    }

    private fun decrypt(encryptedBase64: String): String? {
        val secretKey = getSecretKey()
        if (secretKey == null) {
            return try {
                String(Base64.decode(encryptedBase64, Base64.NO_WRAP), Charsets.UTF_8)
            } catch (_: Exception) {
                null
            }
        }
        return try {
            val combined = Base64.decode(encryptedBase64, Base64.NO_WRAP)
            if (combined.size <= GCM_IV_LENGTH) return null
            val iv = ByteArray(GCM_IV_LENGTH)
            System.arraycopy(combined, 0, iv, 0, GCM_IV_LENGTH)
            val cipherText = ByteArray(combined.size - GCM_IV_LENGTH)
            System.arraycopy(combined, GCM_IV_LENGTH, cipherText, 0, cipherText.size)

            val cipher = Cipher.getInstance(TRANSFORMATION)
            val spec = GCMParameterSpec(GCM_TAG_LENGTH, iv)
            cipher.init(Cipher.DECRYPT_MODE, secretKey, spec)
            String(cipher.doFinal(cipherText), Charsets.UTF_8)
        } catch (_: Exception) {
            null
        }
    }

    fun saveTokens(accessToken: String, refreshToken: String) {
        prefs.edit()
            .putString(KEY_ACCESS_TOKEN, encrypt(accessToken))
            .putString(KEY_REFRESH_TOKEN, encrypt(refreshToken))
            .apply()
    }

    fun saveUserData(userId: String?, email: String?, fullName: String?) {
        prefs.edit()
            .putString(KEY_USER_ID, userId)
            .putString(KEY_USER_EMAIL, email)
            .putString(KEY_USER_NAME, fullName)
            .apply()
    }

    fun getAccessToken(): String? {
        val raw = prefs.getString(KEY_ACCESS_TOKEN, null) ?: return null
        return decrypt(raw)
    }

    fun getRefreshToken(): String? {
        val raw = prefs.getString(KEY_REFRESH_TOKEN, null) ?: return null
        return decrypt(raw)
    }

    fun getUserEmail(): String? = prefs.getString(KEY_USER_EMAIL, null)

    fun getUserName(): String? = prefs.getString(KEY_USER_NAME, null)

    fun getUserId(): String? = prefs.getString(KEY_USER_ID, null)

    fun savePendingFcmToken(token: String) {
        prefs.edit().putString(KEY_PENDING_FCM_TOKEN, encrypt(token)).apply()
    }

    fun getPendingFcmToken(): String? = prefs.getString(KEY_PENDING_FCM_TOKEN, null)?.let(::decrypt)

    fun getDeviceId(): String? = prefs.getString(KEY_DEVICE_ID, null)

    fun getRegisteredFcmToken(): String? = prefs.getString(KEY_REGISTERED_FCM_TOKEN, null)?.let(::decrypt)

    fun saveDeviceRegistration(deviceId: String, token: String) {
        prefs.edit()
            .putString(KEY_DEVICE_ID, deviceId)
            .putString(KEY_REGISTERED_FCM_TOKEN, encrypt(token))
            .remove(KEY_PENDING_FCM_TOKEN)
            .apply()
    }

    fun clearDeviceRegistration() {
        prefs.edit()
            .remove(KEY_DEVICE_ID)
            .remove(KEY_REGISTERED_FCM_TOKEN)
            .apply()
    }

    fun wasNotificationPermissionAsked(): Boolean =
        prefs.getBoolean(KEY_NOTIFICATION_PERMISSION_ASKED, false)

    fun setNotificationPermissionAsked() {
        prefs.edit().putBoolean(KEY_NOTIFICATION_PERMISSION_ASKED, true).apply()
    }

    fun hasValidTokens(): Boolean {
        return !getAccessToken().isNullOrBlank()
    }

    fun clear() {
        prefs.edit()
            .remove(KEY_ACCESS_TOKEN)
            .remove(KEY_REFRESH_TOKEN)
            .remove(KEY_USER_ID)
            .remove(KEY_USER_EMAIL)
            .remove(KEY_USER_NAME)
            .remove(KEY_DEVICE_ID)
            .remove(KEY_REGISTERED_FCM_TOKEN)
            .apply()
    }
}
