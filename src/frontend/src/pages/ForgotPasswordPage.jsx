import { useState } from 'react'
import { Link } from 'react-router-dom'

import { authResetAPI, getErrorMessage } from '../services/api.js'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await authResetAPI.forgot(email.trim())
      setSent(true)
    } catch (err) {
      setError(getErrorMessage(err, 'password.forgot'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page-shell">
      <main className="container-xl flex min-h-screen items-center justify-center py-12">
        <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-slate-100">Quên mật khẩu</h1>
          {sent ? (
            <p className="mt-4 text-sm text-gray-700 dark:text-slate-200">
              Nếu email tồn tại, chúng tôi đã gửi liên kết đặt lại mật khẩu (hiệu lực 1 giờ). Vui lòng kiểm tra hộp thư.
            </p>
          ) : (
            <form className="mt-4 space-y-3" onSubmit={handleSubmit}>
              <input
                type="email"
                placeholder="email@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
              />
              {error && <p className="text-xs text-red-600">{error}</p>}
              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {submitting ? 'Đang gửi...' : 'Gửi liên kết đặt lại'}
              </button>
            </form>
          )}
          <p className="mt-4 text-center text-xs text-gray-500 dark:text-slate-400">
            <Link to="/auth" className="text-blue-600 hover:underline">Quay lại đăng nhập</Link>
          </p>
        </div>
      </main>
    </div>
  )
}
