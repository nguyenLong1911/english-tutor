import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { authResetAPI, getErrorMessage } from '../services/api.js'
import { useAuthStore } from '../stores/authStore.js'
import { getPostAuthPath } from '../utils/routing.js'

// /auth/reset?token=... — landing page from the reset email.
export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const navigate = useNavigate()
  const hydrate = useAuthStore((s) => s.hydrate)

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!token) setError('Token không hợp lệ hoặc đã hết hạn.')
  }, [token])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (password.length < 8) { setError('Mật khẩu cần ít nhất 8 ký tự.'); return }
    if (password !== confirm) { setError('Hai lần nhập không khớp.'); return }
    setSubmitting(true)
    setError(null)
    try {
      await authResetAPI.reset(token, password)
      setDone(true)
      const user = await hydrate()
      setTimeout(() => navigate(getPostAuthPath(user)), 1200)
    } catch (err) {
      setError(getErrorMessage(err, 'password.reset'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page-shell">
      <main className="container-xl flex min-h-screen items-center justify-center py-12">
        <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-slate-100">Đặt lại mật khẩu</h1>
          {done ? (
            <p className="mt-4 text-sm text-green-600">Mật khẩu đã được cập nhật. Đang chuyển hướng...</p>
          ) : (
            <form className="mt-4 space-y-3" onSubmit={handleSubmit}>
              <input
                type="password"
                placeholder="Mật khẩu mới (≥8 ký tự)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                required
              />
              <input
                type="password"
                placeholder="Nhập lại mật khẩu"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                required
              />
              {error && <p className="text-xs text-red-600">{error}</p>}
              <button
                type="submit"
                disabled={submitting || !token}
                className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {submitting ? 'Đang lưu...' : 'Lưu mật khẩu'}
              </button>
              <p className="text-center text-xs text-gray-500 dark:text-slate-400">
                <Link to="/auth" className="text-blue-600 hover:underline">Quay lại đăng nhập</Link>
              </p>
            </form>
          )}
        </div>
      </main>
    </div>
  )
}
