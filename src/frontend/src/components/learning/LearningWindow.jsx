import { useEffect, useState } from 'react'
import RichTextContent from '../common/RichTextContent.jsx'

const SCREEN_TABS = [
  { screen: 'LESSON_READER', label: 'Bài giảng' },
  { screen: 'PRACTICE_RUNNER', label: 'Ôn tập' },
  { screen: 'FLASHCARD_RUNNER', label: 'Flashcard' },
]

const SCREEN_TITLES = {
  LESSON_READER: 'Bài giảng',
  PRACTICE_RUNNER: 'Ôn tập',
  PRACTICE_RESULT: 'Kết quả ôn tập',
  FLASHCARD_RUNNER: 'Flashcard',
  LESSON_COMPLETE: 'Hoàn thành bài',
  CHAT: 'Học theo bài',
}

export default function LearningWindow({
  data,
  dueCount = 0,
  error,
  learnedCount = 0,
  loading,
  onAction,
  onClose,
  onSelectScreen,
  onSubmitPractice,
  open,
  screen,
}) {
  if (!open) return null

  const title = SCREEN_TITLES[screen] || 'Học theo bài'
  const lesson = data?.lesson
  const state = data?.learning_state || data?.state || {}
  const lessonId = getLessonId(data)

  return (
    <div className="h-full overflow-y-auto p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <span className="rounded border border-[#cce4ce] bg-[var(--green-soft)] px-3 py-1 text-xs font-semibold tracking-[0.14em] text-[var(--green)]">
            LEARNING
          </span>
          <h2 className="font-display mt-3 text-3xl font-semibold leading-tight">{title}</h2>
          {lesson?.title ? <p className="mt-2 text-sm leading-snug text-[var(--muted)]">{lesson.title}</p> : null}
        </div>
        <button className="shrink-0 text-[var(--muted)]" onClick={onClose} type="button" aria-label="Đóng cửa sổ học">
          <CloseIcon />
        </button>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-2 rounded-xl border border-[var(--line)] bg-[var(--cream-0)] p-1">
        {SCREEN_TABS.map((tab) => {
          const active = screen === tab.screen || (screen === 'PRACTICE_RESULT' && tab.screen === 'PRACTICE_RUNNER')
          return (
            <button
              className={`rounded-lg px-2 py-2 text-sm font-semibold transition ${active ? 'bg-white text-[var(--ochre)] shadow-sm' : 'text-[var(--muted)] hover:bg-white/70'}`}
              key={tab.screen}
              onClick={() => onSelectScreen(tab.screen)}
              type="button"
            >
              {tab.label}
            </button>
          )
        })}
      </div>

      {state.current_step && state.current_step !== 'NONE' ? (
        <div className="mt-4 flex flex-wrap gap-2 text-xs text-[var(--muted)]">
          <span className="rounded-full bg-[var(--cream-2)] px-3 py-1">Step: {state.current_step}</span>
          {state.active_lesson_id ? <span className="rounded-full bg-[var(--cream-2)] px-3 py-1">{state.active_lesson_id}</span> : null}
        </div>
      ) : null}

      {data?.agent_message ? (
        <div className="mt-4 rounded-xl border-l-4 border-[var(--ochre)] bg-[var(--ochre-soft)] p-4 text-sm leading-relaxed text-[var(--muted)]">
          {data.agent_message}
        </div>
      ) : null}

      {loading ? <PanelState text="Đang tải nội dung học từ backend..." /> : null}
      {error ? <PanelState tone="error" text={error} /> : null}

      {!loading && !error ? (
        <div className="mt-5 border-t border-[var(--line)] pt-5">
          {screen === 'LESSON_READER' ? <LessonReader lesson={lesson} onAction={onAction} /> : null}
          {screen === 'PRACTICE_RUNNER' ? <PracticeRunner data={data} lessonId={lessonId} onAction={onAction} onSubmitPractice={onSubmitPractice} /> : null}
          {screen === 'PRACTICE_RESULT' ? <PracticeResult data={data} onAction={onAction} /> : null}
          {screen === 'FLASHCARD_RUNNER' ? <FlashcardRunner data={data} onAction={onAction} /> : null}
          {screen === 'LESSON_COMPLETE' ? <LessonComplete data={data} onAction={onAction} /> : null}
          {screen === 'CHAT' ? <LearningEmpty dueCount={dueCount} learnedCount={learnedCount} onAction={onAction} /> : null}
        </div>
      ) : null}
    </div>
  )
}

function LessonReader({ lesson, onAction }) {
  if (!lesson) {
    return (
      <div>
        <PanelState text="Chưa có bài học đang mở." />
        <button className="btn btn-primary mt-5 w-full" onClick={() => onAction('START_LEARNING')} type="button">
          Bắt đầu học
        </button>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-5 grid grid-cols-2 gap-3">
        <button className="btn btn-primary min-h-[46px] px-4" onClick={() => onAction('LESSON_PRACTICE')} type="button">
          Ôn tập
        </button>
        <button className="btn btn-ghost min-h-[46px] px-4" onClick={() => onAction('LESSON_FLASHCARD')} type="button">
          Flashcard
        </button>
      </div>
      <MarkdownContent content={lesson.markdown || ''} />
    </div>
  )
}

function PracticeRunner({ data, lessonId, onAction, onSubmitPractice }) {
  const questions = data?.questions || []
  const practiceSetId = data?.practice_set_id || data?.ui_directive?.practice_set_id
  const [answers, setAnswers] = useState({})

  useEffect(() => {
    setAnswers({})
  }, [practiceSetId])

  const answeredCount = questions.filter((question) => String(answers[question.question_id] || '').trim()).length

  if (!questions.length) {
    return (
      <div>
        <PanelState text="Chưa có bộ câu hỏi cho bài này." />
        <button className="btn btn-primary mt-5 w-full" disabled={!lessonId} onClick={() => onAction('LESSON_PRACTICE')} type="button">
          Tạo 12 câu ôn tập
        </button>
      </div>
    )
  }

  const updateAnswer = (questionId, value) => {
    setAnswers((current) => ({ ...current, [questionId]: value }))
  }

  const submit = () => {
    onSubmitPractice(
      questions.map((question) => ({
        question_id: question.question_id,
        answer: String(answers[question.question_id] || '').trim(),
      }))
    )
  }

  return (
    <div>
      <div className="mb-5">
        <div className="flex items-center justify-between text-sm">
          <span className="font-semibold text-[var(--ochre)]">{answeredCount}/{questions.length} câu đã trả lời</span>
          <span className="text-[var(--muted)]">Pass 70%</span>
        </div>
        <div className="mt-3 h-1.5 rounded-full bg-[var(--cream-3)]">
          <div className="h-full rounded-full bg-[var(--ochre-bright)]" style={{ width: `${Math.min(100, (answeredCount / questions.length) * 100)}%` }} />
        </div>
      </div>

      <div className="space-y-5">
        {questions.map((question, index) => (
          <QuestionCard answer={answers[question.question_id] || ''} index={index} key={question.question_id} onAnswer={updateAnswer} question={question} />
        ))}
      </div>

      <button className="btn btn-primary mt-6 w-full" disabled={!practiceSetId || answeredCount === 0} onClick={submit} type="button">
        Nộp câu trả lời
      </button>
    </div>
  )
}

function QuestionCard({ answer, index, onAnswer, question }) {
  const typeLabel = {
    multiple_choice_abcd: 'Trắc nghiệm',
    write_sentence: 'Viết câu',
    vocab_answer: 'Từ vựng',
    quick_definition: 'Định nghĩa nhanh',
  }[question.type] || question.type

  return (
    <section className="rounded-xl border border-[var(--line)] bg-[var(--cream-0)] p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold text-[var(--ochre)]">Câu {index + 1}</p>
        <span className="rounded-full bg-white px-2 py-1 text-xs text-[var(--muted)]">{typeLabel}</span>
      </div>
      <h3 className="mt-3 text-base font-semibold leading-snug">{question.prompt}</h3>
      {question.target_vocab?.length ? <p className="mt-2 text-xs text-[var(--muted)]">Target: {question.target_vocab.join(', ')}</p> : null}

      {question.type === 'multiple_choice_abcd' ? (
        <div className="mt-4 space-y-2">
          {question.choices.map((choice) => (
            <button
              className={`w-full rounded-lg border p-3 text-left text-sm leading-relaxed ${answer === choice.key ? 'border-[var(--ochre)] bg-[var(--ochre-soft)]' : 'border-[var(--line)] bg-white'}`}
              key={choice.key}
              onClick={() => onAnswer(question.question_id, choice.key)}
              type="button"
            >
              <span className="mr-2 font-semibold text-[var(--ochre)]">{choice.key}.</span>
              {choice.text}
            </button>
          ))}
        </div>
      ) : (
        <textarea
          className="mt-4 min-h-[86px] w-full resize-y rounded-xl border border-[var(--line)] bg-white p-3 text-sm leading-relaxed outline-none focus:border-[var(--ochre)]"
          onChange={(event) => onAnswer(question.question_id, event.target.value)}
          placeholder={question.type === 'write_sentence' ? 'Viết câu trả lời của bạn...' : 'Nhập câu trả lời ngắn...'}
          value={answer}
        />
      )}
    </section>
  )
}

function PracticeResult({ data, onAction }) {
  const feedback = data?.feedback || []
  const accuracy = typeof data?.accuracy === 'number' ? Math.round(data.accuracy * 100) : 0

  return (
    <div>
      <div className={`rounded-xl border p-5 ${data?.passed ? 'border-[var(--green)] bg-[var(--green-soft)]' : 'border-[var(--ochre)] bg-[var(--ochre-soft)]'}`}>
        <p className="text-sm font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">Điểm ôn tập</p>
        <p className="font-display mt-2 text-5xl font-semibold">{data?.score ?? 0}/{data?.total ?? 12}</p>
        <p className="mt-2 text-sm text-[var(--muted)]">Accuracy {accuracy}%</p>
      </div>

      {feedback.length ? (
        <div className="mt-5 space-y-3">
          {feedback.map((item, index) => (
            <div className="rounded-xl border border-[var(--line)] bg-[var(--cream-0)] p-4" key={item.question_id}>
              <div className="flex items-center justify-between gap-3">
                <p className="font-semibold">Câu {index + 1}</p>
                <span className={`rounded-full px-2 py-1 text-xs ${item.correct ? 'bg-[var(--green-soft)] text-[var(--green)]' : 'bg-[#fff1eb] text-[var(--red)]'}`}>
                  {item.correct ? 'Đúng' : 'Cần sửa'}
                </span>
              </div>
              <p className="mt-2 text-sm text-[var(--muted)]">Đáp án: {item.correct_answer}</p>
              {item.explanation_vi ? <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">{item.explanation_vi}</p> : null}
            </div>
          ))}
        </div>
      ) : null}

      <SuggestedActions actions={data?.suggested_actions} onAction={onAction} />
    </div>
  )
}

function FlashcardRunner({ data, onAction }) {
  const cards = data?.cards || []
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [reviewed, setReviewed] = useState({})
  const current = cards[index] || null
  const reviewedCount = Object.keys(reviewed).length
  const canComplete = reviewedCount >= cards.length

  useEffect(() => {
    setIndex(0)
    setFlipped(false)
    setReviewed({})
  }, [data?.lesson_id])

  if (!cards.length) {
    return (
      <div>
        <PanelState text="Chưa có flashcards cho bài này." />
        <button className="btn btn-primary mt-5 w-full" onClick={() => onAction('LESSON_FLASHCARD')} type="button">
          Tải flashcards
        </button>
      </div>
    )
  }

  const markCard = () => {
    if (!current) return
    setReviewed((value) => ({ ...value, [current.card_id]: true }))
    setFlipped(false)
    setIndex((value) => Math.min(cards.length - 1, value + 1))
  }

  return (
    <div>
      <div className="mb-5 flex items-center justify-between text-sm">
        <span className="font-semibold text-[var(--ochre)]">{index + 1}/{cards.length} flashcards</span>
        <span className="text-[var(--muted)]">Đã xem {reviewedCount}/{cards.length}</span>
      </div>
      <button
        className="grid min-h-[235px] w-full place-items-center rounded-2xl border border-[var(--line)] bg-[var(--cream-0)] p-6 text-center"
        onClick={() => setFlipped((value) => !value)}
        type="button"
      >
        {!flipped ? (
          <span>
            <span className="font-display block text-4xl font-semibold">{current.front || current.word}</span>
            {current.pos ? <span className="mt-3 block text-sm uppercase tracking-[0.16em] text-[var(--ochre)]">{current.pos}</span> : null}
            <span className="mt-5 block text-sm text-[var(--muted)]">Chạm để xem nghĩa và ví dụ</span>
          </span>
        ) : (
          <span>
            <span className="block text-2xl font-semibold">{current.back?.definition_vi}</span>
            <span className="mt-5 block text-sm italic leading-relaxed text-[var(--muted)]">{current.back?.example}</span>
          </span>
        )}
      </button>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <button className="btn btn-ghost min-h-[46px] px-4" onClick={() => setFlipped((value) => !value)} type="button">
          Lật thẻ
        </button>
        <button className="btn btn-primary min-h-[46px] px-4" onClick={markCard} type="button">
          Đã xem
        </button>
      </div>

      <button
        className={`btn mt-5 w-full ${canComplete ? 'btn-primary' : 'cursor-not-allowed border-[#d5d0c6] bg-[#ece7de] text-[#9a9488] shadow-none'}`}
        disabled={!canComplete}
        onClick={() => onAction('LESSON_COMPLETE')}
        type="button"
      >
        Hoàn thành bài
      </button>
      <SuggestedActions actions={data?.suggested_actions} onAction={onAction} />
    </div>
  )
}

function LessonComplete({ data, onAction }) {
  return (
    <div>
      <div className="rounded-xl border border-[var(--green)] bg-[var(--green-soft)] p-5">
        <p className="text-sm font-semibold uppercase tracking-[0.12em] text-[var(--green)]">Lesson complete</p>
        <p className="mt-3 text-sm leading-relaxed text-[var(--muted)]">
          {data?.completed_lesson_id ? `Bạn đã hoàn thành ${data.completed_lesson_id}.` : 'Bài học đã hoàn thành.'}
        </p>
      </div>
      {data?.next_lesson ? (
        <div className="mt-5 rounded-xl border border-[var(--line)] bg-[var(--cream-0)] p-4">
          <p className="text-sm text-[var(--muted)]">Bài tiếp theo</p>
          <h3 className="mt-2 text-lg font-semibold">{data.next_lesson.title}</h3>
          <button className="btn btn-primary mt-4 w-full" onClick={() => onAction('NEXT_LESSON')} type="button">
            Mở bài tiếp theo
          </button>
        </div>
      ) : null}
      <SuggestedActions actions={data?.suggested_actions} onAction={onAction} />
    </div>
  )
}

function LearningEmpty({ dueCount, learnedCount, onAction }) {
  return (
    <div>
      <PanelState text="Cửa sổ này sẽ tự mở đúng màn hình khi backend gửi ui_directive.action = OPEN." />
      <button className="btn btn-primary mt-5 w-full" onClick={() => onAction('START_LEARNING')} type="button">
        Bắt đầu học
      </button>
      <div className="mt-6 grid grid-cols-2 gap-3">
        <StatBox label="Từ đang theo dõi" value={learnedCount} />
        <StatBox label="Đến hạn ôn" value={dueCount} />
      </div>
    </div>
  )
}

function SuggestedActions({ actions = [], onAction }) {
  if (!actions.length) return null
  return (
    <div className="mt-5 grid gap-2">
      {actions.map((action) => (
        <button className="rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-left text-sm font-semibold text-[var(--muted)] hover:border-[var(--ochre)] hover:text-[var(--ochre)]" key={`${action.intent}-${action.label}`} onClick={() => onAction(action.intent)} type="button">
          {action.label}
        </button>
      ))}
    </div>
  )
}

function MarkdownContent({ content }) {
  if (!content.trim()) return <PanelState text="Bài học chưa có markdown để hiển thị." />
  return <RichTextContent content={content} />
}

function StatBox({ label, value }) {
  return (
    <div className="rounded-xl border border-[var(--line)] bg-[var(--cream-0)] p-4">
      <p className="text-xs text-[var(--muted)]">{label}</p>
      <p className="font-display mt-2 text-3xl font-semibold">{value}</p>
    </div>
  )
}

function PanelState({ text, tone = 'muted' }) {
  return (
    <div className={`mt-4 rounded-xl border p-4 text-sm leading-relaxed ${tone === 'error' ? 'border-[var(--red)] bg-[#fff1eb] text-[var(--red)]' : 'border-[var(--line)] bg-[var(--cream-0)] text-[var(--muted)]'}`}>
      {text}
    </div>
  )
}

function getLessonId(data) {
  return data?.lesson_id || data?.ui_directive?.lesson_id || data?.learning_state?.active_lesson_id || data?.state?.active_lesson_id || data?.lesson?.lesson_id || null
}

function IconBase({ children }) {
  return <svg aria-hidden="true" className="h-5 w-5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.9" viewBox="0 0 24 24">{children}</svg>
}

function CloseIcon() { return <IconBase><path d="M18 6 6 18" /><path d="m6 6 12 12" /></IconBase> }
