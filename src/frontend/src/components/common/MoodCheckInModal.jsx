import { useEffect, useState } from 'react'
import { useMoodStore } from '../../stores/moodStore.js'

const MOODS = [
  { id: 'sleepy', emoji: '😴', label: 'Buồn ngủ' },
  { id: 'neutral', emoji: '😐', label: 'Bình thường' },
  { id: 'ok', emoji: '🙂', label: 'Ổn' },
  { id: 'happy', emoji: '😊', label: 'Vui' },
  { id: 'fire', emoji: '🔥', label: 'Hăng' },
]

// Mood-Adaptive Sessions (§9.1) — appears at the start of a session every 8h.
export default function MoodCheckInModal({ open, onClose }) {
  const setMood = useMoodStore((s) => s.setMood)
  const markAsked = useMoodStore((s) => s.markAsked)
  const [selected, setSelected] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) setSelected(null)
  }, [open])

  if (!open) return null

  const handlePick = async (mood) => {
    setSelected(mood)
    setSubmitting(true)
    try {
      await setMood(mood)
    } finally {
      markAsked()
      setSubmitting(false)
      onClose?.()
    }
  }

  const handleSkip = () => {
    markAsked()
    onClose?.()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="mood-title"
    >
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl dark:bg-slate-900">
        <h2 id="mood-title" className="text-lg font-semibold text-gray-900 dark:text-slate-100">
          Hôm nay bạn cảm thấy thế nào?
        </h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-slate-400">
          Luna sẽ điều chỉnh độ dài và độ khó của phiên học theo tâm trạng của bạn.
        </p>
        <div className="mt-5 grid grid-cols-5 gap-2">
          {MOODS.map((m) => (
            <button
              key={m.id}
              type="button"
              disabled={submitting}
              onClick={() => handlePick(m.id)}
              aria-pressed={selected === m.id}
              className={`flex flex-col items-center gap-1 rounded-xl border px-2 py-3 text-sm transition focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                selected === m.id
                  ? 'border-blue-500 bg-blue-50 dark:border-sky-400 dark:bg-sky-950'
                  : 'border-gray-200 bg-white hover:bg-gray-50 dark:border-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700'
              }`}
              title={m.label}
            >
              <span className="text-2xl" aria-hidden="true">{m.emoji}</span>
              <span className="text-xs text-gray-700 dark:text-slate-300">{m.label}</span>
            </button>
          ))}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={handleSkip}
            className="rounded-lg px-3 py-2 text-sm text-gray-500 hover:bg-gray-100 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            Bỏ qua
          </button>
        </div>
      </div>
    </div>
  )
}
