import { useEffect } from 'react'
import { useBriefStore } from '../../stores/briefStore.js'

const QUALITY_OPTIONS = [
  {
    value: 0,
    title: 'Sai hẳn',
    description: 'Không nhớ ra hoặc trả lời sai hoàn toàn.',
    selectedClass: 'border-rose-300 bg-rose-50 text-rose-900',
    idleClass: 'border-gray-200 bg-white text-gray-700 hover:border-rose-200 hover:bg-rose-50/70',
  },
  {
    value: 2,
    title: 'Nhớ mang máng',
    description: 'Chỉ nhận ra sau khi xem đáp án.',
    selectedClass: 'border-amber-300 bg-amber-50 text-amber-900',
    idleClass: 'border-gray-200 bg-white text-gray-700 hover:border-amber-200 hover:bg-amber-50/70',
  },
  {
    value: 4,
    title: 'Đúng nhưng chậm',
    description: 'Tự nhớ ra được, nhưng còn ngập ngừng.',
    selectedClass: 'border-sky-300 bg-sky-50 text-sky-900',
    idleClass: 'border-gray-200 bg-white text-gray-700 hover:border-sky-200 hover:bg-sky-50/70',
  },
  {
    value: 5,
    title: 'Nhớ ngay',
    description: 'Trả lời đúng gần như ngay lập tức.',
    selectedClass: 'border-emerald-300 bg-emerald-50 text-emerald-900',
    idleClass: 'border-gray-200 bg-white text-gray-700 hover:border-emerald-200 hover:bg-emerald-50/70',
  },
]

const getTodayKey = () => new Date().toISOString().slice(0, 10)

// Morning Brief (§9.4): inline overlay shown the first time the user opens
// the app each day. Three retrieval prompts with delayed reveal + reflection.
export default function MorningBriefOverlay({ onClose }) {
  const {
    date,
    questions,
    loading,
    submitting,
    submitted,
    error,
    load,
    setAnswer,
    reveal,
    rate,
    submit,
    reset,
  } = useBriefStore()

  useEffect(() => {
    if (!loading && !error && date !== getTodayKey()) load()
  }, [date, error, load, loading])

  if (loading) {
    return (
      <Overlay>
        <p className="text-sm text-gray-600 dark:text-slate-300">Đang tải brief sáng nay...</p>
      </Overlay>
    )
  }

  if (error) {
    return (
      <Overlay>
        <p className="text-sm text-red-600">{error}</p>
        <Footer onClose={onClose} />
      </Overlay>
    )
  }

  if (!submitted && questions.length === 0) {
    return (
      <Overlay>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Hôm nay không có gì cần ôn</h2>
        <p className="mt-2 text-sm text-gray-500 dark:text-slate-400">Bạn có thể bắt đầu phiên học mới bất kỳ lúc nào.</p>
        <Footer
          onClose={() => {
            reset()
            onClose?.()
          }}
          primaryLabel="Bắt đầu học"
        />
      </Overlay>
    )
  }

  if (submitted) {
    return (
      <Overlay>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--ochre)]">Morning Brief</p>
            <h2 className="mt-1 text-xl font-semibold text-gray-900 dark:text-slate-100">Đã lưu kết quả ôn tập</h2>
          </div>
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">
            {questions.length}/{questions.length} câu
          </span>
        </div>

        <p className="mt-2 text-sm text-gray-500 dark:text-slate-400">
          Bạn vẫn có thể xem lại đáp án đúng trước khi đóng màn hình này.
        </p>

        <div className="mt-4 space-y-4">
          {questions.map((q, idx) => (
            <ResultCard key={q.word_id} index={idx} question={q} />
          ))}
        </div>

        <Footer
          onClose={() => {
            reset()
            onClose?.()
          }}
          primaryLabel="Bắt đầu học"
        />
      </Overlay>
    )
  }

  const reviewedCount = questions.filter((q) => Number.isInteger(q.quality)).length
  const canSubmit = questions.length > 0 && reviewedCount === questions.length

  const handleSubmit = async () => {
    await submit()
  }

  return (
    <Overlay>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--ochre)]">Morning Brief</p>
          <h2 className="mt-1 text-xl font-semibold text-gray-900 dark:text-slate-100">3 câu ôn tập đầu ngày</h2>
        </div>
        <span className="rounded-full bg-[var(--ochre-soft)] px-3 py-1 text-xs font-semibold text-[var(--ochre)]">
          {reviewedCount}/{questions.length} đã tự đánh giá
        </span>
      </div>

      <p className="mt-2 text-sm text-gray-500 dark:text-slate-400">
        Thử nhớ trước, sau đó bấm <span className="font-medium text-gray-700 dark:text-slate-200">Xem đáp án</span> rồi chọn mức bạn nhớ được để Luna lên lịch ôn tiếp.
      </p>

      <div className="mt-4 space-y-4">
        {questions.map((q, idx) => (
          <div key={q.word_id} className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-gray-900 dark:text-slate-100">Câu {idx + 1}</p>
              {Number.isInteger(q.quality) ? (
                <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                  {getQualityOption(q.quality)?.title}
                </span>
              ) : null}
            </div>

            <p className="mt-2 text-sm font-medium leading-6 text-gray-900 dark:text-slate-100">{q.prompt_vi}</p>

            <label className="mt-3 block">
              <span className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500 dark:text-slate-400">Câu trả lời của bạn</span>
              <textarea
                value={q.userAnswer}
                onChange={(e) => setAnswer(idx, e.target.value)}
                placeholder="Bạn có thể gõ câu trả lời ra đây hoặc tự trả lời trong đầu."
                rows={3}
                className="mt-2 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm leading-6 text-gray-800 outline-none transition focus:border-[var(--ochre)] focus:ring-2 focus:ring-[var(--ochre-soft)] dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
              />
            </label>

            {!q.revealed ? (
              <button
                type="button"
                onClick={() => reveal(idx)}
                className="mt-3 inline-flex rounded-xl border border-[var(--ochre)] bg-[var(--ochre-soft)] px-4 py-2 text-sm font-medium text-[var(--ochre)] transition hover:bg-[#f7dfc1]"
              >
                Xem đáp án
              </button>
            ) : (
              <>
                <AnswerBlock answer={q.answer} example={q.example} />

                <div className="mt-4">
                  <p className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500 dark:text-slate-400">
                    Bạn nhớ ở mức nào?
                  </p>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    {QUALITY_OPTIONS.map((option) => {
                      const active = q.quality === option.value
                      return (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => rate(idx, option.value)}
                          aria-pressed={active}
                          className={`rounded-2xl border px-4 py-3 text-left text-sm transition ${
                            active ? option.selectedClass : option.idleClass
                          } dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100`}
                        >
                          <span className="block font-semibold">{option.title}</span>
                          <span className="mt-1 block text-xs leading-5 text-current/80">{option.description}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              </>
            )}
          </div>
        ))}
      </div>

      <Footer
        onClose={onClose}
        primaryLabel={submitting ? 'Đang lưu...' : 'Lưu kết quả'}
        primaryAction={handleSubmit}
        primaryDisabled={!canSubmit || submitting}
      />
    </Overlay>
  )
}

function Overlay({ children }) {
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/50 p-4 sm:items-center">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-[28px] bg-[var(--cream-0)] p-6 shadow-xl dark:bg-slate-900 sm:p-7">
        {children}
      </div>
    </div>
  )
}

function Footer({ onClose, primaryLabel, primaryAction, primaryDisabled }) {
  return (
    <div className="mt-6 flex flex-col-reverse gap-2 border-t border-gray-200 pt-4 sm:flex-row sm:justify-end dark:border-slate-700">
      <button
        type="button"
        onClick={onClose}
        className="rounded-xl px-4 py-2 text-sm font-medium text-gray-500 transition hover:bg-gray-100 dark:text-slate-400 dark:hover:bg-slate-800"
      >
        Đóng
      </button>
      {primaryLabel ? (
        <button
          type="button"
          onClick={primaryAction || onClose}
          disabled={primaryDisabled}
          className="rounded-xl bg-[var(--ochre)] px-4 py-2 text-sm font-semibold text-white transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {primaryLabel}
        </button>
      ) : null}
    </div>
  )
}

function AnswerBlock({ answer, example }) {
  return (
    <div className="mt-4 rounded-2xl border border-[#d9e6c9] bg-[#f5faef] p-4 dark:border-emerald-900/60 dark:bg-emerald-950/30">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-emerald-700 dark:text-emerald-300">Đáp án đúng</p>
      <p className="mt-2 text-sm font-medium leading-6 text-gray-900 dark:text-slate-100">{answer}</p>
      {example ? <p className="mt-2 text-sm italic leading-6 text-gray-600 dark:text-slate-300">{example}</p> : null}
    </div>
  )
}

function ResultCard({ index, question }) {
  const quality = getQualityOption(question.quality)
  const evaluation = getAnswerEvaluation(question.answer_correct)

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-gray-900 dark:text-slate-100">Câu {index + 1}</p>
          <p className="mt-1 text-sm text-gray-600 dark:text-slate-300">{question.prompt_vi}</p>
        </div>
        {quality ? (
          <span className="rounded-full bg-[var(--ochre-soft)] px-2.5 py-1 text-xs font-semibold text-[var(--ochre)]">
            {quality.title}
          </span>
        ) : null}
      </div>

      {evaluation ? (
        <div className={`mt-3 inline-flex rounded-full px-3 py-1 text-xs font-semibold ${evaluation.className}`}>
          {evaluation.label}
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <InfoBlock
          label="Bạn đã trả lời"
          value={question.userAnswer?.trim() || 'Bạn không nhập câu trả lời, chỉ tự nhớ trong đầu.'}
        />
        <InfoBlock label="Đáp án đúng" value={question.answer} accent="success" />
      </div>

      {question.example ? (
        <p className="mt-3 text-sm italic leading-6 text-gray-500 dark:text-slate-400">{question.example}</p>
      ) : null}

      {question.next_review ? (
        <p className="mt-3 text-xs font-medium uppercase tracking-[0.14em] text-gray-500 dark:text-slate-400">
          Lần ôn tiếp theo: <span className="text-gray-700 dark:text-slate-200">{formatDate(question.next_review)}</span>
        </p>
      ) : null}

      {question.brief_skip_until ? (
        <p className="mt-2 text-xs font-medium uppercase tracking-[0.14em] text-gray-500 dark:text-slate-400">
          Bỏ qua Morning Brief đến: <span className="text-gray-700 dark:text-slate-200">{formatDate(question.brief_skip_until)}</span>
        </p>
      ) : null}
    </div>
  )
}

function InfoBlock({ label, value, accent = 'default' }) {
  const accentClass =
    accent === 'success'
      ? 'border-[#d9e6c9] bg-[#f5faef] dark:border-emerald-900/60 dark:bg-emerald-950/30'
      : 'border-gray-200 bg-gray-50 dark:border-slate-700 dark:bg-slate-800'

  return (
    <div className={`rounded-2xl border p-3 ${accentClass}`}>
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500 dark:text-slate-400">{label}</p>
      <p className="mt-2 text-sm leading-6 text-gray-800 dark:text-slate-100">{value}</p>
    </div>
  )
}

function getQualityOption(value) {
  return QUALITY_OPTIONS.find((option) => option.value === value) || null
}

function getAnswerEvaluation(value) {
  if (value === true) {
    return {
      label: 'Hệ thống ghi nhận: đúng, sẽ bỏ qua kỳ Morning Brief tiếp theo',
      className: 'bg-emerald-100 text-emerald-700',
    }
  }
  if (value === false) {
    return {
      label: 'Hệ thống ghi nhận: sai, đã đưa vào Personal Error Review',
      className: 'bg-rose-100 text-rose-700',
    }
  }
  return null
}

function formatDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date)
}
