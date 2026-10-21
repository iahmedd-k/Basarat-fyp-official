package com.fyp.basarattradeinvest.feature.auth

import android.text.Editable
import android.text.TextWatcher
import android.view.KeyEvent
import android.view.View
import android.widget.EditText

class OtpInputHelper(
    private val editTexts: List<EditText>,
    private val onCodeChanged: (code: String, isComplete: Boolean) -> Unit
) {

    private var isUpdating = false

    init {
        require(editTexts.size == 6) { "OtpInputHelper requires exactly 6 EditText inputs." }
        setupListeners()
    }

    private fun setupListeners() {
        for (i in editTexts.indices) {
            val current = editTexts[i]

            current.addTextChangedListener(object : TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}

                override fun afterTextChanged(s: Editable?) {
                    if (isUpdating) return
                    val text = s?.toString().orEmpty()

                    // Handle paste of multiple characters (e.g., 6-digit code copied)
                    if (text.length > 1) {
                        isUpdating = true
                        val digits = text.filter { it.isDigit() }
                        for (j in editTexts.indices) {
                            if (j < digits.length) {
                                editTexts[j].setText(digits[j].toString())
                            } else {
                                editTexts[j].text?.clear()
                            }
                        }
                        val focusIndex = digits.length.coerceAtMost(5)
                        editTexts[focusIndex].requestFocus()
                        editTexts[focusIndex].setSelection(editTexts[focusIndex].text.length)
                        isUpdating = false
                        notifyChange()
                        return
                    }

                    if (text.isNotEmpty()) {
                        // Move to next digit
                        if (i < 5) {
                            editTexts[i + 1].requestFocus()
                        }
                    }
                    notifyChange()
                }
            })

            current.setOnKeyListener(View.OnKeyListener { _, keyCode, event ->
                if (event.action == KeyEvent.ACTION_DOWN && keyCode == KeyEvent.KEYCODE_DEL) {
                    if (current.text.isNullOrEmpty() && i > 0) {
                        editTexts[i - 1].requestFocus()
                        editTexts[i - 1].text?.clear()
                        return@OnKeyListener true
                    }
                }
                false
            })
        }
    }

    private fun notifyChange() {
        val code = getCode()
        onCodeChanged(code, code.length == 6)
    }

    fun getCode(): String {
        val sb = StringBuilder()
        for (et in editTexts) {
            val char = et.text?.toString().orEmpty()
            if (char.isNotEmpty()) {
                sb.append(char)
            }
        }
        return sb.toString()
    }

    fun clear() {
        isUpdating = true
        for (et in editTexts) {
            et.text?.clear()
        }
        isUpdating = false
        editTexts.firstOrNull()?.requestFocus()
        notifyChange()
    }

    fun setEnabled(enabled: Boolean) {
        for (et in editTexts) {
            et.isEnabled = enabled
        }
    }
}
