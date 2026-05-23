import { useState } from 'react'
import { contextAPI, getErrorMessage } from '../../services/api.js'

// Context Injection (§9.2): paste an English email/document → mini lesson.
export default function ContextPasteBox({ onLessonReady }) {
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [lesson, setLesson] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!text.trim() || text.length > 4096) return
    setSubmitting(true)
    setError(null)
    try {
      const data = await contextAPI.analyze(text)
      setLesson(data)
      onLessonReady?.(data)
    } catch (err) {
      setError(getErrorMessage(err, 'context.analyze'))
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
      >
        <span aria-hidden="true">📋</span> Dán ngữ cảnh công việc
      </button>
    )
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-slate-100">Ngữ cảnh công việc</h3>
        <button
          type="button"
          onClick={() => { setOpen(false); setLesson(null); setError(null) }}
          className="text-xs text-gray-500 hover:text-gray-700 dark:text-slate-400"
        >
          Đóng
        </button>
      </div>
      <form onSubmit={handleSubmit}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          maxLength={4096}
          placeholder="Dán email, đoạn báo cáo, mô tả công việc tiếng Anh ở đây (≤4KB)..."
          className="w-full resize-y rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:placeholder-slate-500"
        />
        <div className="mt-2 flex items-center justify-between">
          <span className="text-xs text-gray-500 dark:text-slate-400">{text.length}/4096</span>
          <button
            type="submit"
            disabled={submitting || !text.trim()}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? 'Đang phân tích...' : 'Phân tích'}
          </button>
        </div>
      </form>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {lesson && (
        <div className="mt-4 rounded-lg bg-blue-50 p-3 dark:bg-sky-950">
          <p className="text-sm font-semibold text-blue-900 dark:text-sky-200">Mini-lesson</p>
          <p className="mt-1 whitespace-pre-wrap text-sm text-gray-800 dark:text-slate-200">{lesson.mini_lesson}</p>
          {lesson.terms?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1">
              {lesson.terms.map((t) => (
                <span key={t} className="rounded-full bg-white px-2 py-0.5 text-xs text-blue-700 dark:bg-slate-800 dark:text-sky-300">
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
