import React, { useState, useEffect } from 'react'
import { authApi } from '../api/auth'
import OtpInput from './OtpInput'

export default function ForgotPasswordFlow({ onBackToLogin, onCompleteLogin }) {
  // Steps: 'email' (1) -> 'code' (2) -> 'password' (3) -> 'success'
  const [step, setStep] = useState('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isResending, setIsResending] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [cooldown, setCooldown] = useState(30)

  useEffect(() => {
    if (step !== 'code' || cooldown <= 0) return
    const timer = setInterval(() => {
      setCooldown((c) => c - 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [step, cooldown])

  // Step 1: Request 6-digit reset code
  async function handleSendEmail(e) {
    e.preventDefault()
    setError('')
    setMessage('')

    if (!email.trim() || !email.includes('@')) {
      setError('Please enter a valid email address.')
      return
    }

    setIsLoading(true)
    try {
      const res = await authApi.forgotPassword(email.trim())
      setMessage(res.message || 'If that email exists, a 6-digit reset code has been sent.')
      setCooldown(30)
      setStep('code')
    } catch (err) {
      setError(err.message || 'Failed to send reset code. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  // Step 2: Verify 6-digit code to acquire reset_token
  async function handleVerifyCode(e) {
    if (e) e.preventDefault()
    setError('')
    setMessage('')

    if (code.length < 6) {
      setError('Please enter the complete 6-digit reset code.')
      return
    }

    setIsLoading(true)
    try {
      const res = await authApi.verifyResetCode(email.trim(), code.trim())
      if (!res.reset_token) {
        throw new Error('Server did not return a valid reset authorization.')
      }
      setResetToken(res.reset_token)
      setMessage('Code verified. Please set your new password.')
      setStep('password')
    } catch (err) {
      setError(err.message || 'Invalid or expired reset code.')
    } finally {
      setIsLoading(false)
    }
  }

  // Resend code in Step 2
  async function handleResendCode() {
    if (cooldown > 0 || isResending) return
    setError('')
    setMessage('')

    setIsResending(true)
    try {
      await authApi.forgotPassword(email.trim())
      setMessage('A new 6-digit reset code has been sent to your email.')
      setCooldown(30)
    } catch (err) {
      setError(err.message || 'Failed to resend reset code.')
    } finally {
      setIsResending(false)
    }
  }

  // Step 3: Update password using reset_token
  async function handleResetPassword(e) {
    e.preventDefault()
    setError('')
    setMessage('')

    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters with 1 uppercase letter, 1 number, and 1 special character.')
      return
    }

    setIsLoading(true)
    try {
      const res = await authApi.resetPassword({
        reset_token: resetToken,
        new_password: password,
        confirm_password: confirmPassword,
      })
      setMessage(res.message || 'Password updated successfully. You can sign in now.')
      setStep('success')
    } catch (err) {
      setError(err.message || 'Failed to reset password. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const stepNumber = step === 'email' ? 1 : step === 'code' ? 2 : 3

  return (
    <div className="auth-card forgot-password-card">
      {/* Step Indicator */}
      <div className="auth-step-indicator" role="navigation" aria-label="Password Reset Progress">
        <div className={`step-chip ${stepNumber >= 1 ? 'active' : ''} ${stepNumber > 1 ? 'completed' : ''}`}>
          <span className="step-num">1</span>
          <span className="step-label">Email</span>
        </div>
        <div className="step-arrow">→</div>
        <div className={`step-chip ${stepNumber >= 2 ? 'active' : ''} ${stepNumber > 2 ? 'completed' : ''}`}>
          <span className="step-num">2</span>
          <span className="step-label">Verify Code</span>
        </div>
        <div className="step-arrow">→</div>
        <div className={`step-chip ${stepNumber === 3 ? 'active' : ''}`}>
          <span className="step-num">3</span>
          <span className="step-label">New Password</span>
        </div>
      </div>

      {/* STEP 1: ENTER EMAIL */}
      {step === 'email' && (
        <>
          <div className="auth-heading">
            <p className="eyebrow">Account recovery</p>
            <h2>Forgot Password</h2>
            <p>Enter your email address to receive a 6-digit password reset code.</p>
          </div>

          <form onSubmit={handleSendEmail} className="recovery-form" noValidate>
            <label className="field">
              <span>Email address</span>
              <input
                required
                type="email"
                name="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  setError('')
                }}
                placeholder="you@example.com"
                autoComplete="email"
                disabled={isLoading}
              />
            </label>

            {error && <p className="form-error" role="alert">{error}</p>}
            {message && <p className="form-success" role="status">{message}</p>}

            <button type="submit" className="submit-button" disabled={isLoading || !email}>
              {isLoading ? 'Sending code…' : 'Send Verification Code'}
              {!isLoading && <span aria-hidden="true">→</span>}
            </button>
          </form>
        </>
      )}

      {/* STEP 2: VERIFY RESET CODE */}
      {step === 'code' && (
        <>
          <div className="auth-heading">
            <p className="eyebrow">Step 2 of 3</p>
            <h2>Verify Code</h2>
            <p>
              Enter the 6-digit code sent to:
              <br />
              <strong className="text-emerald-700 font-medium">{email}</strong>
            </p>
          </div>

          <form onSubmit={handleVerifyCode} className="otp-form" noValidate>
            <label className="field-label" style={{ marginBottom: '12px', display: 'block' }}>
              <span>6-Digit Reset Code</span>
            </label>

            <OtpInput
              length={6}
              value={code}
              onChange={(val) => {
                setCode(val)
                setError('')
              }}
              disabled={isLoading}
              hasError={Boolean(error)}
            />

            {error && <p className="form-error" role="alert">{error}</p>}
            {message && <p className="form-success" role="status">{message}</p>}

            <button
              type="submit"
              className="submit-button"
              disabled={isLoading || code.length < 6}
              style={{ marginTop: '20px' }}
            >
              {isLoading ? 'Verifying code…' : 'Verify Code'}
              {!isLoading && <span aria-hidden="true">→</span>}
            </button>

            <div className="otp-resend-container">
              <p className="text-xs text-slate-500 mb-1">Didn't receive the code?</p>
              {cooldown > 0 ? (
                <span className="otp-cooldown-text">
                  Resend available in <strong className="font-semibold text-emerald-700">{cooldown}s</strong>
                </span>
              ) : (
                <button
                  type="button"
                  className="text-button otp-resend-button"
                  onClick={handleResendCode}
                  disabled={isResending}
                >
                  {isResending ? 'Sending…' : 'Resend Code'}
                </button>
              )}
            </div>
          </form>
        </>
      )}

      {/* STEP 3: CREATE NEW PASSWORD */}
      {step === 'password' && (
        <>
          <div className="auth-heading">
            <p className="eyebrow">Step 3 of 3</p>
            <h2>Create New Password</h2>
            <p>Choose a secure password you have not used before.</p>
          </div>

          <form onSubmit={handleResetPassword} className="recovery-form" noValidate>
            <label className="field">
              <span>New Password</span>
              <input
                required
                type="password"
                name="password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value)
                  setError('')
                }}
                placeholder="Enter your new password"
                autoComplete="new-password"
                disabled={isLoading}
              />
            </label>

            <label className="field">
              <span>Confirm Password</span>
              <input
                required
                type="password"
                name="confirmPassword"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value)
                  setError('')
                }}
                placeholder="Repeat your new password"
                autoComplete="new-password"
                disabled={isLoading}
              />
            </label>

            <p className="password-hint">
              Use 8+ characters with at least one uppercase letter, one number, and one special character.
            </p>

            {error && <p className="form-error" role="alert">{error}</p>}
            {message && <p className="form-success" role="status">{message}</p>}

            <button
              type="submit"
              className="submit-button"
              disabled={isLoading || !password || !confirmPassword}
            >
              {isLoading ? 'Updating password…' : 'Update Password'}
              {!isLoading && <span aria-hidden="true">→</span>}
            </button>
          </form>
        </>
      )}

      {/* SUCCESS STATE */}
      {step === 'success' && (
        <div className="auth-success-box text-center" style={{ padding: '20px 0' }}>
          <div className="auth-heading">
            <div className="success-icon" style={{ fontSize: '42px', marginBottom: '12px' }}>✓</div>
            <h2>Password Reset Successful</h2>
            <p>{message || 'Your password has been updated. You can sign in now.'}</p>
          </div>

          <button
            type="button"
            className="submit-button"
            onClick={onCompleteLogin}
            style={{ marginTop: '24px' }}
          >
            Go to Sign In <span aria-hidden="true">→</span>
          </button>
        </div>
      )}

      {step !== 'success' && (
        <button type="button" className="back-button" onClick={onBackToLogin}>
          ← Back to sign in
        </button>
      )}
    </div>
  )
}

