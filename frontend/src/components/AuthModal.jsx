import React, { useState, useEffect, useRef } from 'react'
import { authApi, saveSession } from '../api/auth'

export default function AuthModal({
  isOpen,
  initialMode = 'login', // 'login' | 'signup' | 'verify' | 'forgot'
  initialEmail = '',
  onClose,
  onAuthenticated,
}) {
  const [mode, setMode] = useState(initialMode)
  const [email, setEmail] = useState(initialEmail)
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  // Verify Email states
  const [verifyCode, setVerifyCode] = useState('')
  const [resendCooldown, setResendCooldown] = useState(0)

  // Forgot Password flow states: 'request' | 'verify' | 'reset'
  const [forgotStep, setForgotStep] = useState('request')
  const [resetToken, setResetToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmNewPassword, setConfirmNewPassword] = useState('')

  // Status & error states
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [unverifiedEmail, setUnverifiedEmail] = useState('')

  const modalRef = useRef(null)

  // Reset or sync mode when initialMode or isOpen changes
  useEffect(() => {
    if (isOpen) {
      setMode(initialMode)
      setError('')
      setMessage('')
      if (initialEmail) setEmail(initialEmail)
      else if (!email) {
        const pending = localStorage.getItem('basarat_pending_verify_email')
        if (pending) setEmail(pending)
      }
      if (initialMode === 'verify' && resendCooldown <= 0) {
        setResendCooldown(120)
      }
    }
  }, [isOpen, initialMode, initialEmail])

  // Cooldown countdown for OTP resends
  useEffect(() => {
    if (resendCooldown <= 0) return
    const timer = setInterval(() => {
      setResendCooldown((prev) => prev - 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [resendCooldown])

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose?.()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  // Switch between modes with clean resets
  const switchMode = (targetMode) => {
    setMode(targetMode)
    setError('')
    setMessage('')
    setUnverifiedEmail('')
    if (targetMode === 'verify' && resendCooldown <= 0) {
      setResendCooldown(120)
    }
    if (targetMode === 'forgot') setForgotStep('request')
  }

  // 1. Handle Login Submit
  async function handleLogin(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    setUnverifiedEmail('')

    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address.')
      return
    }
    if (!password) {
      setError('Please enter your password.')
      return
    }

    setIsSubmitting(true)
    try {
      const response = await authApi.login({
        email: email.trim(),
        password,
      })
      saveSession(response)
      onAuthenticated?.(response.user)
      onClose?.()
    } catch (err) {
      if (err.status === 403 || err.message?.toLowerCase().includes('not verified')) {
        setUnverifiedEmail(email.trim())
        setError('Your account is not verified yet. Please enter the verification code sent to your email.')
      } else {
        setError(err.message || 'Invalid email or password.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  // 2. Handle Signup Submit
  async function handleSignup(e) {
    e.preventDefault()
    setError('')
    setMessage('')

    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address.')
      return
    }
    if (!password) {
      setError('Password is required.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters with 1 uppercase letter, 1 number, and 1 special character.')
      return
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      await authApi.signup({
        email: email.trim(),
        password,
        full_name: fullName.trim() || null,
      })
      localStorage.setItem('basarat_pending_verify_email', email.trim())
      setResendCooldown(120)
      setMessage('Account created! A 6-digit verification code was sent to your email.')
      setMode('verify')
    } catch (err) {
      setError(err.message || 'Failed to create account. Please check your details.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // 3. Handle Verify Email
  async function handleVerifyEmail(e) {
    e.preventDefault()
    setError('')
    setMessage('')

    if (!email.trim()) {
      setError('Email address is required.')
      return
    }
    if (verifyCode.trim().length < 6) {
      setError('Please enter the full 6-digit verification code.')
      return
    }

    setIsSubmitting(true)
    try {
      const response = await authApi.verifyEmail(email.trim(), verifyCode.trim())
      saveSession(response)
      localStorage.removeItem('basarat_pending_verify_email')
      onAuthenticated?.(response.user)
      onClose?.()
    } catch (err) {
      setError(err.message || 'Verification failed. Please check the code and try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // 4. Resend Verification Code
  async function handleResendVerification() {
    if (resendCooldown > 0) return
    setError('')
    setMessage('')
    try {
      await authApi.resendVerification(email.trim())
      setResendCooldown(120)
      setMessage('A new 6-digit verification code has been dispatched to your email.')
    } catch (err) {
      setError(err.message || 'Could not resend code. Please try again in a few moments.')
    }
  }

  // 5. Handle Forgot Password Flow
  async function handleForgotRequest(e) {
    e.preventDefault()
    setError('')
    setMessage('')

    if (!email.trim() || !email.includes('@')) {
      setError('Please enter a valid email address.')
      return
    }

    setIsSubmitting(true)
    try {
      const res = await authApi.forgotPassword(email.trim())
      setMessage(res.message || 'If an account exists for this email, a 6-digit code has been sent.')
      setResendCooldown(30)
      setForgotStep('verify')
    } catch (err) {
      setError(err.message || 'Failed to request password reset.')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleForgotVerifyCode(e) {
    e.preventDefault()
    setError('')
    setMessage('')

    if (verifyCode.trim().length < 6) {
      setError('Please enter the full 6-digit reset code.')
      return
    }

    setIsSubmitting(true)
    try {
      const res = await authApi.verifyResetCode(email.trim(), verifyCode.trim())
      setResetToken(res.reset_token)
      setMessage('Code confirmed. Please set your new password.')
      setForgotStep('reset')
    } catch (err) {
      setError(err.message || 'Invalid or expired reset code.')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleForgotResetPassword(e) {
    e.preventDefault()
    setError('')
    setMessage('')

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters with 1 uppercase letter, 1 number, and 1 special character.')
      return
    }
    if (newPassword !== confirmNewPassword) {
      setError('Passwords do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      await authApi.resetPassword({
        reset_token: resetToken,
        email: email.trim(),
        code: verifyCode.trim(),
        new_password: newPassword,
        confirm_password: confirmNewPassword,
      })
      setMessage('Password updated successfully! Please sign in with your new credentials.')
      setPassword('')
      setMode('login')
    } catch (err) {
      setError(err.message || 'Failed to update password. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose?.()
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
    >
      <div
        ref={modalRef}
        className="relative w-full max-w-[430px] bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-100 dark:border-slate-800 p-6 sm:p-8 transition-all scale-100 animate-in zoom-in-95 duration-150 overflow-hidden"
      >
        {/* Close Button (Top-Right X) */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 sm:top-5 sm:right-5 p-1.5 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
          aria-label="Close dialog"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>

        {/* Modal Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 text-[11px] font-bold uppercase tracking-wider mb-2">
            Basarat PSX
          </div>
          <h2 id="auth-modal-title" className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            {mode === 'login' && 'Sign in to Basarat'}
            {mode === 'signup' && 'Create your account'}
            {mode === 'verify' && 'Verify your email'}
            {mode === 'forgot' && 'Reset your password'}
          </h2>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            {mode === 'login' && 'Welcome back! Please sign in to continue'}
            {mode === 'signup' && 'Start investing with intelligent PSX analytics'}
            {mode === 'verify' && `We sent a 6-digit code to ${email || 'your email'}`}
            {mode === 'forgot' && (forgotStep === 'request' ? 'Enter your email to receive a recovery code' : forgotStep === 'verify' ? 'Enter the 6-digit code sent to your email' : 'Choose a strong new password')}
          </p>
        </div>

        {/* Informational Message Banner */}
        {message && (
          <div className="mb-4 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300 text-xs flex items-start gap-2">
            <svg className="w-4 h-4 shrink-0 text-emerald-600 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            <span>{message}</span>
          </div>
        )}

        {/* Error Alert Banner */}
        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-2">
            <svg className="w-4 h-4 shrink-0 text-rose-500 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <div className="flex-1">
              <p>{error}</p>
              {unverifiedEmail && (
                <button
                  type="button"
                  onClick={() => {
                    setEmail(unverifiedEmail)
                    switchMode('verify')
                  }}
                  className="mt-1.5 font-semibold text-emerald-600 hover:text-emerald-700 underline text-xs cursor-pointer block"
                >
                  Enter verification code now →
                </button>
              )}
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* MODE: LOGIN */}
        {/* ============================================================ */}
        {mode === 'login' && (
          <form onSubmit={handleLogin} className="space-y-3.5" noValidate>
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Email address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => { setEmail(e.target.value); setError('') }}
                placeholder="investor@example.com"
                autoComplete="email"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder:text-slate-400 text-sm focus:outline-hidden focus:ring-2 focus:ring-slate-900 dark:focus:ring-emerald-500 transition-all"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => switchMode('forgot')}
                  className="text-xs font-medium text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 transition-colors cursor-pointer"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError('') }}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  className="w-full pl-3.5 pr-10 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder:text-slate-400 text-sm focus:outline-hidden focus:ring-2 focus:ring-slate-900 dark:focus:ring-emerald-500 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 cursor-pointer"
                  tabIndex={-1}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {/* Dark Continue Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full mt-5 py-2.5 px-4 rounded-xl bg-[#1e2329] hover:bg-[#0d0d0d] text-white font-medium text-sm flex items-center justify-center gap-2 shadow-xs transition-all cursor-pointer active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <>
                  <svg className="animate-spin w-4 h-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>Signing in…</span>
                </>
              ) : (
                <>
                  <span>Continue</span>
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polygon points="5 3 19 12 5 21 5 3" fill="currentColor" />
                  </svg>
                </>
              )}
            </button>

            {/* Bottom Switcher */}
            <div className="pt-4 mt-4 border-t border-slate-100 dark:border-slate-800 text-center text-xs text-slate-500 dark:text-slate-400">
              Don’t have an account?{' '}
              <button
                type="button"
                onClick={() => switchMode('signup')}
                className="font-semibold text-slate-900 dark:text-white hover:underline cursor-pointer"
              >
                Sign up
              </button>
            </div>
          </form>
        )}

        {/* ============================================================ */}
        {/* MODE: SIGNUP */}
        {/* ============================================================ */}
        {mode === 'signup' && (
          <form onSubmit={handleSignup} className="space-y-3" noValidate>
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Full name <span className="text-slate-400 font-normal">(optional)</span>
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Your name"
                autoComplete="name"
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder:text-slate-400 text-sm focus:outline-hidden focus:ring-2 focus:ring-slate-900 dark:focus:ring-emerald-500 transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Email address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => { setEmail(e.target.value); setError('') }}
                placeholder="investor@example.com"
                autoComplete="email"
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder:text-slate-400 text-sm focus:outline-hidden focus:ring-2 focus:ring-slate-900 dark:focus:ring-emerald-500 transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError('') }}
                  placeholder="Min 8 chars, 1 uppercase, 1 digit, 1 symbol"
                  autoComplete="new-password"
                  className="w-full pl-3.5 pr-10 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder:text-slate-400 text-sm focus:outline-hidden focus:ring-2 focus:ring-slate-900 dark:focus:ring-emerald-500 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 cursor-pointer"
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Confirm password
              </label>
              <div className="relative">
                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  required
                  value={confirmPassword}
                  onChange={(e) => { setConfirmPassword(e.target.value); setError('') }}
                  placeholder="Repeat your password"
                  autoComplete="new-password"
                  className="w-full pl-3.5 pr-10 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder:text-slate-400 text-sm focus:outline-hidden focus:ring-2 focus:ring-slate-900 dark:focus:ring-emerald-500 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 cursor-pointer"
                  tabIndex={-1}
                >
                  {showConfirmPassword ? (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <p className="text-[11px] text-slate-400 leading-tight">
              Password must include at least 8 characters, 1 uppercase letter, 1 number, and 1 special symbol (!@#$%^&*).
            </p>

            {/* Dark Continue Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full mt-4 py-2.5 px-4 rounded-xl bg-[#1e2329] hover:bg-[#0d0d0d] text-white font-medium text-sm flex items-center justify-center gap-2 shadow-xs transition-all cursor-pointer active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <>
                  <svg className="animate-spin w-4 h-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>Creating account…</span>
                </>
              ) : (
                <>
                  <span>Create Account</span>
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polygon points="5 3 19 12 5 21 5 3" fill="currentColor" />
                  </svg>
                </>
              )}
            </button>

            {/* Bottom Switcher */}
            <div className="pt-3 mt-3 border-t border-slate-100 dark:border-slate-800 text-center text-xs text-slate-500 dark:text-slate-400">
              Already have an account?{' '}
              <button
                type="button"
                onClick={() => switchMode('login')}
                className="font-semibold text-slate-900 dark:text-white hover:underline cursor-pointer"
              >
                Sign in
              </button>
            </div>
          </form>
        )}

        {/* ============================================================ */}
        {/* MODE: VERIFY EMAIL (6-digit OTP) */}
        {/* ============================================================ */}
        {mode === 'verify' && (
          <form onSubmit={handleVerifyEmail} className="space-y-4" noValidate>
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                6-digit verification code
              </label>
              <input
                type="text"
                required
                maxLength={6}
                value={verifyCode}
                onChange={(e) => {
                  const val = e.target.value.replace(/\D/g, '')
                  setVerifyCode(val)
                  setError('')
                }}
                placeholder="123456"
                autoComplete="one-time-code"
                className="w-full text-center tracking-[0.5em] font-mono text-lg py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-slate-900 dark:focus:ring-emerald-500"
              />
            </div>

            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>Didn’t get code?</span>
              <button
                type="button"
                disabled={resendCooldown > 0}
                onClick={handleResendVerification}
                className="font-semibold text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {resendCooldown > 0 ? `Resend in ${Math.floor(resendCooldown / 60)}:${String(resendCooldown % 60).padStart(2, '0')}` : 'Resend code'}
              </button>
            </div>

            <button
              type="submit"
              disabled={isSubmitting || verifyCode.trim().length < 6}
              className="w-full py-2.5 px-4 rounded-xl bg-[#1e2329] hover:bg-[#0d0d0d] text-white font-medium text-sm flex items-center justify-center gap-2 shadow-xs transition-all cursor-pointer active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Verifying…' : 'Verify Email & Continue'}
            </button>

            <div className="text-center pt-3 border-t border-slate-100 dark:border-slate-800 text-xs">
              <button
                type="button"
                onClick={() => switchMode('login')}
                className="text-slate-500 hover:text-slate-800 dark:hover:text-slate-300 cursor-pointer"
              >
                ← Back to Sign in
              </button>
            </div>
          </form>
        )}

        {/* ============================================================ */}
        {/* MODE: FORGOT PASSWORD */}
        {/* ============================================================ */}
        {mode === 'forgot' && (
          <div className="space-y-4">
            {forgotStep === 'request' && (
              <form onSubmit={handleForgotRequest} className="space-y-4" noValidate>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                    Account email address
                  </label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setError('') }}
                    placeholder="investor@example.com"
                    autoComplete="email"
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder:text-slate-400 text-sm focus:outline-hidden focus:ring-2 focus:ring-slate-900 dark:focus:ring-emerald-500"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full py-2.5 px-4 rounded-xl bg-[#1e2329] hover:bg-[#0d0d0d] text-white font-medium text-sm flex items-center justify-center gap-2 shadow-xs transition-all cursor-pointer active:scale-[0.98]"
                >
                  {isSubmitting ? 'Sending code…' : 'Send Recovery Code'}
                </button>
              </form>
            )}

            {forgotStep === 'verify' && (
              <form onSubmit={handleForgotVerifyCode} className="space-y-4" noValidate>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                    6-digit reset code
                  </label>
                  <input
                    type="text"
                    required
                    maxLength={6}
                    value={verifyCode}
                    onChange={(e) => {
                      const val = e.target.value.replace(/\D/g, '')
                      setVerifyCode(val)
                      setError('')
                    }}
                    placeholder="123456"
                    className="w-full text-center tracking-[0.5em] font-mono text-lg py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isSubmitting || verifyCode.trim().length < 6}
                  className="w-full py-2.5 px-4 rounded-xl bg-[#1e2329] hover:bg-[#0d0d0d] text-white font-medium text-sm flex items-center justify-center gap-2 shadow-xs transition-all cursor-pointer active:scale-[0.98]"
                >
                  {isSubmitting ? 'Verifying code…' : 'Confirm Code'}
                </button>
              </form>
            )}

            {forgotStep === 'reset' && (
              <form onSubmit={handleForgotResetPassword} className="space-y-3" noValidate>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    New password
                  </label>
                  <input
                    type="password"
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Min 8 chars, 1 uppercase, 1 digit, 1 symbol"
                    className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder:text-slate-400 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Confirm new password
                  </label>
                  <input
                    type="password"
                    required
                    value={confirmNewPassword}
                    onChange={(e) => setConfirmNewPassword(e.target.value)}
                    placeholder="Repeat new password"
                    className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder:text-slate-400 text-sm"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full mt-3 py-2.5 px-4 rounded-xl bg-[#1e2329] hover:bg-[#0d0d0d] text-white font-medium text-sm flex items-center justify-center gap-2 shadow-xs transition-all cursor-pointer active:scale-[0.98]"
                >
                  {isSubmitting ? 'Updating password…' : 'Set New Password'}
                </button>
              </form>
            )}

            <div className="text-center pt-3 border-t border-slate-100 dark:border-slate-800 text-xs">
              <button
                type="button"
                onClick={() => switchMode('login')}
                className="text-slate-500 hover:text-slate-800 dark:hover:text-slate-300 cursor-pointer"
              >
                ← Back to Sign in
              </button>
            </div>
          </div>
        )}

        {/* Subtle Trust Footer */}
        <div className="mt-5 text-center">
          <p className="text-[10px] text-slate-400 dark:text-slate-500">
            Secured by <span className="font-semibold text-slate-600 dark:text-slate-400">Basarat Engine</span>
          </p>
        </div>
      </div>
    </div>
  )
}

