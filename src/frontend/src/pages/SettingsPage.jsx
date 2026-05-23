import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import BottomNav from '../components/common/BottomNav.jsx'
import { gdprAPI, getErrorMessage, tutorAPI } from '../services/api.js'
import { useAuthStore } from '../stores/authStore.js'
import { useThemeStore } from '../stores/themeStore.js'

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user)
  const clear = useAuthStore((s) => s.clear)
  const status = useAuthStore((s) => s.status)
  const theme = useThemeStore((s) => s.theme)
  const setTheme = useThemeStore((s) => s.setTheme)
  const navigate = useNavigate()

  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [cefr, setCefr] = useState(user?.cefr_level || 'B1')
  const [industry, setIndustry] = useState(user?.industry || '')
  const [preferredStudyTime, setPreferredStudyTime] = useState(user?.preferred_study_time || '')
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileMsg, setProfileMsg] = useState(null)

  const [confirmOpen, setConfirmOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(null)

  if (status === 'unauthenticated') {
    navigate('/auth')
    return null
  }
  if (!user) return null

  const saveProfile = async (e) => {
    e.preventDefault()
    setSavingProfile(true)
    setProfileMsg(null)
    try {
      await tutorAPI.updateUserPreferences(user.user_id, {
        display_name: displayName,
        cefr_level: cefr,
        industry,
        learning_goals: user.learning_goals,
        preferred_study_time: preferredStudyTime,
      })
      setProfileMsg('Đã cập nhật.')
    } catch (err) {
      setProfileMsg(getErrorMessage(err, 'profile.save'))
    } finally {
      setSavingProfile(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    setDeleteError(null)
    const started = Date.now()
    try {
      await gdprAPI.delete(password || undefined)
      const elapsed = Date.now() - started
      console.info('GDPR delete completed in', elapsed, 'ms')
      clear()
      navigate('/')
    } catch (err) {
      setDeleteError(getErrorMessage(err, 'gdpr.delete'))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="page-shell pb-24">
      <header className="sticky top-0 z-30 border-b border-[var(--line)] bg-[rgba(255,250,247,0.88)] backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
        <div className="container-xl flex min-h-[64px] items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-900 dark:text-slate-100">⚙️ Cài đặt</h1>
        </div>
      </header>

      <main className="container-xl space-y-6 py-6">
        {/* Profile */}
        <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100">Hồ sơ</h2>
          <form className="mt-3 space-y-3" onSubmit={saveProfile}>
            <Field label="Tên hiển thị">
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="input"
              />
            </Field>
            <Field label="CEFR">
              <select value={cefr} onChange={(e) => setCefr(e.target.value)} className="input">
                {['A1', 'A2', 'B1', 'B2', 'C1'].map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
            </Field>
            <Field label="Ngành nghề">
              <input value={industry} onChange={(e) => setIndustry(e.target.value)} className="input" />
            </Field>
            <Field label="Thời lượng học ưa thích">
              <select value={preferredStudyTime} onChange={(e) => setPreferredStudyTime(e.target.value)} className="input">
                <option value="">Chưa chọn</option>
                {['5 phút', '10 phút', '20 phút', '30 phút', '60 phút+'].map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </Field>
            <button
              type="submit"
              disabled={savingProfile}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {savingProfile ? 'Đang lưu...' : 'Lưu thay đổi'}
            </button>
            {profileMsg && <p className="text-xs text-gray-500 dark:text-slate-400">{profileMsg}</p>}
          </form>
        </section>

        {/* Theme */}
        <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100">Giao diện</h2>
          <div className="mt-3 inline-flex overflow-hidden rounded-lg border border-gray-200 dark:border-slate-700">
            {['light', 'dark'].map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTheme(t)}
                aria-pressed={theme === t}
                className={`px-4 py-2 text-sm ${
                  theme === t
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-50 dark:bg-slate-800 dark:text-slate-200'
                }`}
              >
                {t === 'light' ? 'Sáng' : 'Tối'}
              </button>
            ))}
          </div>
        </section>

        {/* GDPR */}
        <section className="rounded-2xl border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/40">
          <h2 className="text-sm font-semibold text-red-700 dark:text-red-300">Xóa toàn bộ dữ liệu (GDPR · C-07)</h2>
          <p className="mt-1 text-sm text-red-700/80 dark:text-red-300/80">
            Tác vụ này xóa toàn bộ hồ sơ, từ vựng, lịch sử chat, mood, DNA. Hoàn tất trong &lt;30 giây và không thể khôi phục.
          </p>
          {!confirmOpen ? (
            <button
              type="button"
              onClick={() => setConfirmOpen(true)}
              className="mt-3 rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100 dark:border-red-700 dark:bg-slate-900 dark:text-red-300"
            >
              Yêu cầu xóa dữ liệu
            </button>
          ) : (
            <div className="mt-3 space-y-2">
              {user.email && user.cefr_level !== undefined && (
                <input
                  type="password"
                  placeholder="Nhập mật khẩu để xác nhận"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input"
                />
              )}
              {deleteError && <p className="text-xs text-red-600">{deleteError}</p>}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={deleting}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {deleting ? 'Đang xóa...' : 'Tôi hiểu, xóa ngay'}
                </button>
                <button
                  type="button"
                  onClick={() => { setConfirmOpen(false); setPassword(''); setDeleteError(null) }}
                  className="rounded-lg px-3 py-2 text-sm text-gray-500 hover:bg-gray-100 dark:text-slate-400 dark:hover:bg-slate-800"
                >
                  Hủy
                </button>
              </div>
            </div>
          )}
        </section>
      </main>

      <BottomNav />

      <style>{`
        .input { width:100%; border-radius:0.5rem; border:1px solid #e5e7eb; padding:0.5rem 0.75rem; font-size:0.875rem; background:#fff; }
        .dark .input { border-color: rgb(51 65 85); background: rgb(15 23 42); color: rgb(241 245 249); }
      `}</style>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-700 dark:text-slate-300">{label}</span>
      {children}
    </label>
  )
}
