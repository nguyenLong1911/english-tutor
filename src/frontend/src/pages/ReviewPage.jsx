import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import BottomNav from '../components/common/BottomNav.jsx'
import LoadingSpinner from '../components/common/LoadingSpinner.jsx'
import SM2FeedbackButtons from '../components/review/SM2FeedbackButtons.jsx'
import { getErrorMessage, tutorAPI } from '../services/api.js'
import { useAuthStore } from '../stores/authStore.js'

export default function ReviewPage() {
  const user = useAuthStore((s) => s.user)
  const status = useAuthStore((s) => s.status)
  const navigate = useNavigate()

  const [items, setItems] = useState([])
  const [index, setIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [revealed, setRevealed] = useState(false)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (status === 'unauthenticated') navigate('/auth')
  }, [status, navigate])

  useEffect(() => {
    if (!user?.user_id) return
    let cancelled = false
    setLoading(true)
    tutorAPI
      .getReviewDue(user.user_id, 20)
      .then((data) => {
        if (cancelled) return
        const list = Array.isArray(data) ? data : data?.items || []
        setItems(list)
        setLoading(false)
      })
      .catch((err) => {
        if (cancelled) return
        setError(getErrorMessage(err, 'review.load'))
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [user?.user_id])

  const current = items[index]

  const handleQuality = async (quality) => {
    if (!current || submitting) return
    setSubmitting(true)
    try {
      await tutorAPI.submitReview(user.user_id, current, quality)
      setRevealed(false)
      setIndex((i) => i + 1)
    } catch (err) {
      setError(getErrorMessage(err, 'review.submit'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page-shell pb-24">
      <header className="sticky top-0 z-30 border-b border-[var(--line)] bg-[rgba(255,250,247,0.88)] backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
        <div className="container-xl flex min-h-[64px] items-center justify-between gap-4">
          <h1 className="text-lg font-semibold text-gray-900 dark:text-slate-100">📝 Ôn tập từ vựng</h1>
          <span className="text-sm text-gray-500 dark:text-slate-400">{items.length === 0 ? '0' : `${index + 1}/${items.length}`}</span>
        </div>
      </header>

      <main className="container-xl py-8">
        {loading && <LoadingSpinner label="Đang tải thẻ ôn tập..." />}
        {error && <p className="text-sm text-red-600">{error}</p>}
        {!loading && !error && items.length === 0 && (
          <EmptyState />
        )}
        {!loading && !error && current && (
          <div className="mx-auto max-w-xl rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-slate-400">
              {current.card_kind === 'error' ? `${current.error_type || 'error'} · personal correction` : `${current.pos} · interval ${current.interval_days}d`}
            </p>
            <h2 className={current.card_kind === 'error' ? 'mt-2 text-xl font-semibold leading-snug text-gray-900 dark:text-slate-100' : 'mt-2 text-3xl font-semibold text-gray-900 dark:text-slate-100'}>
              {current.card_kind === 'error' ? current.front : current.word}
            </h2>
            {!revealed ? (
              <button
                type="button"
                onClick={() => setRevealed(true)}
                className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Hiện đáp án
              </button>
            ) : (
              <div className="mt-4 space-y-3">
                {current.card_kind === 'error' ? (
                  <>
                    <p className="text-sm font-medium text-gray-800 dark:text-slate-100">{current.back}</p>
                    {current.explanation_vi && <p className="text-sm text-gray-700 dark:text-slate-200">{current.explanation_vi}</p>}
                    {current.cloze_text && <p className="text-sm italic text-gray-500 dark:text-slate-400">{current.cloze_text}</p>}
                  </>
                ) : (
                  <>
                    <p className="text-sm text-gray-700 dark:text-slate-200">{current.definition_vi}</p>
                    {current.example && <p className="text-sm italic text-gray-500 dark:text-slate-400">{current.example}</p>}
                  </>
                )}
                <div className="pt-2">
                  <SM2FeedbackButtons onSelect={handleQuality} disabled={submitting} />
                </div>
              </div>
            )}
          </div>
        )}
        {!loading && !error && items.length > 0 && index >= items.length && (
          <p className="mt-6 text-center text-sm text-gray-600 dark:text-slate-300">
            🎉 Bạn đã hoàn thành phiên ôn hôm nay!
          </p>
        )}
      </main>

      <BottomNav />
    </div>
  )
}

function EmptyState() {
  return (
    <div className="mx-auto max-w-md rounded-2xl border border-dashed border-gray-300 bg-white p-8 text-center dark:border-slate-700 dark:bg-slate-900">
      <p className="text-3xl">🎯</p>
      <p className="mt-2 text-sm text-gray-700 dark:text-slate-200">Không có thẻ nào đến hạn ôn.</p>
      <p className="mt-1 text-xs text-gray-500 dark:text-slate-400">Hãy tiếp tục luyện chat để nạp thêm từ mới.</p>
    </div>
  )
}
