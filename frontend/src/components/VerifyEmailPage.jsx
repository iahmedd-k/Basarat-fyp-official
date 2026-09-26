import React, { useState, useEffect } from 'react'
import { authApi, saveSession } from '../api/auth'
import OtpInput from './OtpInput'

export default function VerifyEmailPage({
  email: initialEmail,
  onVerified,
  onBackToLogin,
}) {
  const [email, setEmail] = useState(initialEmail || localStorage.getItem('basarat_pending_verify_email') || '')
  const [code, setCode] = useState('')
  const [isVerifying, setIsVerifying] = useState(false)
  const [isResending, setIsResending] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [cooldown, setCooldown] = useState(120)

  useEffect(() => {
    if (email) {
      localStorage.setItem('basarat_pending_verify_email', email)
    }
  }, [email])

  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setInterval(() => {
      setCooldown((c) => c - 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [cooldown])

  async function handleVerify(e) {
    if (e) e.preventDefault()
    setError('')
    setInfo('')

    if (!email.trim()) {
      setError('Email address is required.')
      return
    }

    if (code.length < 6) {
      setError('Please enter the full 6-digit verification code.')
      return
    }

    setIsVerifying(true)
    try {
      const response = await authApi.verifyEmail(email.trim(), code.trim())
      saveSession(response)
      localStorage.removeItem('basarat_pending_verify_email')
      onVerified(response.user, response)
    } catch (err) {
      setError(err.message || 'Verification failed. Please check the code and try again.')
    } finally {
      setIsVerifying(false)
    }
  }

  async function handleResend() {
    if (cooldown > 0 || isResending) return
    setError('')
    setInfo('')

    if (!email.trim()) {
      setError('Please provide your email address to resend code.')
      return
    }

    setIsResending(true)
    try {
      await authApi.resendVerification(email.trim())
      setInfo('A new 6-digit verification code has been sent to your email.')
      setCooldown(120)
    } catch (err) {
      setError(err.message || 'Failed to resend code. Please try again.')
    } finally {
      setIsResending(false)
    }
  }

  return (
    <div className="auth-card verify-email-card">
      <div className="auth-heading">
        <p className="eyebrow">Account verification</p>
        <h2>Verify Your Email</h2>
        <p>
          We've sent a 6-digit verification code to:
          <br />
          <strong className="text-emerald-700 font-medium">{email || 'your email'}</strong>
        </p>
      </div>

      {!email && (
        <div className="field" style={{ marginTop: '16px' }}>
          <span>Email address</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />
        </div>
      )}

      <form onSubmit={handleVerify} className="otp-form" noValidate>
        <label className="field-label" style={{ marginBottom: '12px', display: 'block' }}>
          <span>Enter 6-digit verification code</span>
        </label>

        <OtpInput
          length={6}
          value={code}
          onChange={(val) => {
            setCode(val)
            setError('')
            if (val.length === 6) {
              // Auto-submit when 6 digits are typed
            }
          }}
          disabled={isVerifying}
          hasError={Boolean(error)}
        />

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        {info && (
          <p className="form-success" role="status">
            {info}
          </p>
        )}

        <button
          type="submit"
          className="submit-button"
          disabled={isVerifying || code.length < 6}
          style={{ marginTop: '20px' }}
        >
          {isVerifying ? 'Verifying email…' : 'Verify Email'}
          {!isVerifying && <span aria-hidden="true">→</span>}
        </button>

        <div className="otp-resend-container">
          <p className="text-xs text-slate-500 mb-1">Didn't receive the code?</p>
          {cooldown > 0 ? (
            <span className="otp-cooldown-text">
              Resend available in <strong className="font-semibold text-emerald-700">{Math.floor(cooldown / 60)}:{String(cooldown % 60).padStart(2, '0')}</strong>
            </span>
          ) : (
            <button
              type="button"
              className="text-button otp-resend-button"
              onClick={handleResend}
              disabled={isResending}
            >
              {isResending ? 'Sending…' : 'Resend Code'}
            </button>
          )}
        </div>
      </form>

      <button type="button" className="back-button" onClick={onBackToLogin}>
        ← Back to sign in
      </button>
    </div>
  )
}

