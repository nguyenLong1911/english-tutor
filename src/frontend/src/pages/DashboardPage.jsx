import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import BottomNav from '../components/common/BottomNav.jsx'
import LoadingSpinner from '../components/common/LoadingSpinner.jsx'
import ErrorDnaRadar from '../components/dashboard/ErrorDnaRadar.jsx'
import { getErrorMessage, tutorAPI } from '../services/api.js'
import { useAuthStore } from '../stores/authStore.js'

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user)
  const status = useAuthStore((s) => s.status)
  const navigate = useNavigate()

  const [summary, setSummary] = useState(null)
  const [vocab, setVocab] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (status === 'unauthenticated') navigate('/auth')
  }, [status, navigate])

  useEffect(() => {
    if (!user?.user_id) return
    Promise.all([
      tutorAPI.getAnalyticsSummary(user.user_id),
      tutorAPI.getAnalyticsVocabulary(user.user_id),
    ])
      .then(([s, v]) => { setSummary(s); setVocab(v) })
      .catch((err) => setError(getErrorMessage(err, 'analytics.load')))
  }, [user?.user_id])

  if (status !== 'authenticated' || !user) {
    return <div className="page-shell"><div className="container-xl py-12"><LoadingSpinner /></div></div>
  }

  return (
    <div className="page-shell pb-24">
      <header className="sticky top-0 z-30 border-b border-[var(--line)] bg-[rgba(255,250,247,0.88)] backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
        <div className="container-xl flex min-h-[64px] items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-900 dark:text-slate-100">📊 Báo cáo tiến độ</h1>
          <span className="text-sm text-gray-500 dark:text-slate-400">{user.display_name || user.email}</span>
        </div>
      </header>

      <main className="container-xl space-y-6 py-6">
        {error && <p className="text-sm text-red-600">{error}</p>}

        <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-slate-100">Hồ sơ học tập</h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <ProfileField label="Tên" value={summary?.profile?.display_name || user.display_name || '—'} />
            <ProfileField label="Email" value={summary?.profile?.email || user.email || '—'} />
            <ProfileField label="CEFR" value={summary?.profile?.cefr_level || user.cefr_level || '—'} />
            <ProfileField label="Ngành" value={summary?.profile?.industry || user.industry || '—'} />
          </div>
        </section>

        <section className="grid gap-4 sm:grid-cols-3">
          <Stat label="Đã học" value={vocab?.total_learned ?? '—'} suffix="từ" />
          <Stat label="Đã thuộc" value={vocab?.mastered ?? '—'} suffix="từ" />
          <Stat label="Lượt ôn" value={summary?.vocabulary?.total_reviews ?? '—'} suffix="lần" />
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-slate-100">Độ chính xác 30 ngày</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={summary?.accuracy_trend || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} interval={4} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Line type="monotone" dataKey="accuracy" stroke="#2563eb" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        <ErrorDnaRadar userId={user.user_id} />

        <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-slate-100">Lỗi sai gần đây</h3>
          {(summary?.recent_errors || []).length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-slate-400">Chưa đủ dữ liệu.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {summary.recent_errors.map((e) => (
                <li key={e.id} className="rounded-lg bg-gray-50 px-3 py-2 dark:bg-slate-800">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium text-gray-700 dark:text-slate-200">{e.error_pattern || e.error_type}</span>
                    <span className="font-mono text-xs text-gray-500 dark:text-slate-400">{e.error_type}</span>
                  </div>
                  {e.corrected_text && (
                    <p className="mt-1 text-xs text-gray-500 dark:text-slate-400">Sửa gợi ý: {e.corrected_text}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-slate-100">Lỗi phổ biến theo loại</h3>
          {(summary?.common_error_types || []).length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-slate-400">Chưa đủ dữ liệu.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {summary.common_error_types.map((e) => (
                <li key={e.error} className="flex justify-between rounded-lg bg-gray-50 px-3 py-2 dark:bg-slate-800">
                  <span className="text-gray-700 dark:text-slate-200">{e.label || e.error}</span>
                  <span className="font-mono text-gray-500 dark:text-slate-400">{e.count}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>

      <BottomNav />
    </div>
  )
}

function ProfileField({ label, value }) {
  return (
    <div className="rounded-xl bg-gray-50 px-3 py-2 dark:bg-slate-800">
      <p className="text-[11px] uppercase tracking-wide text-gray-500 dark:text-slate-400">{label}</p>
      <p className="mt-1 text-sm text-gray-900 dark:text-slate-100">{value}</p>
    </div>
  )
}

function Stat({ label, value, suffix }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
      <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-slate-100">
        {value} <span className="text-sm font-normal text-gray-500 dark:text-slate-400">{suffix}</span>
      </p>
    </div>
  )
}
