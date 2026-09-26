import React, { useRef, useEffect } from 'react'

export default function OtpInput({
  length = 6,
  value = '',
  onChange,
  disabled = false,
  autoFocus = true,
  hasError = false,
}) {
  const inputRefs = useRef([])

  useEffect(() => {
    if (autoFocus && inputRefs.current[0] && !disabled) {
      inputRefs.current[0].focus()
    }
  }, [autoFocus, disabled])

  const digits = Array.from({ length }, (_, i) => value[i] || '')

  function handleChange(e, index) {
    const char = e.target.value.slice(-1)
    if (char && !/^\d$/.test(char)) return

    const newDigits = [...digits]
    newDigits[index] = char
    const nextValue = newDigits.join('')
    onChange(nextValue)

    if (char && index < length - 1) {
      inputRefs.current[index + 1]?.focus()
    }
  }

  function handleKeyDown(e, index) {
    if (e.key === 'Backspace') {
      if (!digits[index] && index > 0) {
        inputRefs.current[index - 1]?.focus()
        const newDigits = [...digits]
        newDigits[index - 1] = ''
        onChange(newDigits.join(''))
      } else {
        const newDigits = [...digits]
        newDigits[index] = ''
        onChange(newDigits.join(''))
      }
    } else if (e.key === 'ArrowLeft' && index > 0) {
      e.preventDefault()
      inputRefs.current[index - 1]?.focus()
    } else if (e.key === 'ArrowRight' && index < length - 1) {
      e.preventDefault()
      inputRefs.current[index + 1]?.focus()
    }
  }

  function handlePaste(e) {
    e.preventDefault()
    if (disabled) return
    const pasted = e.clipboardData.getData('text').trim()
    const numeric = pasted.replace(/\D/g, '').slice(0, length)
    if (!numeric) return
    onChange(numeric)
    const nextIndex = Math.min(numeric.length, length - 1)
    inputRefs.current[nextIndex]?.focus()
  }

  return (
    <div className={`otp-container ${hasError ? 'has-error' : ''}`} onPaste={handlePaste}>
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(el) => (inputRefs.current[index] = el)}
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={1}
          value={digit}
          disabled={disabled}
          autoComplete={index === 0 ? 'one-time-code' : 'off'}
          className={`otp-digit-input ${digit ? 'filled' : ''}`}
          onChange={(e) => handleChange(e, index)}
          onKeyDown={(e) => handleKeyDown(e, index)}
          aria-label={`Digit ${index + 1} of ${length}`}
        />
      ))}
    </div>
  )
}

