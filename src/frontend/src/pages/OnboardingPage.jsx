import { useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { getErrorMessage, tutorAPI } from '../services/api.js'
import { useAuthStore } from '../stores/authStore.js'

const levels = [
  { value: 'A1', title: 'Người mới bắt đầu', text: 'Tôi chỉ biết một vài từ cơ bản.', icon: RabbitIcon },
  { value: 'A2', title: 'Cơ bản', text: 'Tôi có thể giao tiếp các tình huống đơn giản.', icon: WalkIcon },
  { value: 'B1', title: 'Trung cấp', text: 'Tôi có thể duy trì cuộc hội thoại cơ bản.', icon: HatIcon },
  { value: 'C1', title: 'Cao cấp', text: 'Tôi có thể sử dụng ngôn ngữ linh hoạt.', icon: RocketIcon },
]

const occupations = [
  { value: 'tech', label: 'Kỹ sư / Developer' },
  { value: 'general', label: 'Kinh doanh / Sales' },
  { value: 'marketing', label: 'Marketing' },
  { value: 'design', label: 'Thiết kế' },
  { value: 'healthcare', label: 'Y tế' },
  { value: 'education', label: 'Giáo dục' },
  { value: 'finance', label: 'Tài chính' },
  { value: 'general', label: 'Khác' },
]

const interests = ['Công nghệ', 'Du lịch', 'Thể thao', 'Âm nhạc', 'Phim ảnh', 'Ẩm thực', 'Đọc sách', 'Game', 'Thời trang', 'Khoa học']

const goals = [
  { value: 'Giao tiếp hàng ngày', title: 'Giao tiếp hàng ngày', text: 'Nói chuyện tự tin với người nước ngoài', icon: MessageIcon },
  { value: 'Công việc & Email', title: 'Công việc & Email', text: 'Viết email, thuyết trình, họp quốc tế', icon: BriefcaseIcon },
  { value: 'Thi cử IELTS TOEIC', title: 'Thi cử (IELTS/TOEIC)', text: 'Chuẩn bị cho kỳ thi cụ thể', icon: CertificateIcon },
  { value: 'Du học / Định cư', title: 'Du học / Định cư', text: 'Chuẩn bị cho môi trường nước ngoài', icon: PlaneIcon },
]

const styles = [
  { value: 'Giải thích chi tiết, có lý do', icon: BookIcon },
  { value: 'Ngắn gọn, đi thẳng vào vấn đề', icon: BoltIcon },
  { value: 'Nhiều ví dụ thực tế', icon: BulbIcon },
  { value: 'Sửa lỗi ngay lập tức', icon: PencilIcon },
]

const times = ['5 phút', '10 phút', '20 phút', '30 phút', '60 phút+']

const totalSteps = 6

export default function OnboardingPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const currentUser = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)
  const [step, setStep] = useState(1)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [completed, setCompleted] = useState(false)
  const [answers, setAnswers] = useState({
    cefr_level: '',
    industry: '',
    industryLabel: '',
    interests: [],
    goal: '',
    style: '',
    time: '',
  })

  const progress = completed ? 100 : Math.round((step / totalSteps) * 100)
  const canContinue = useMemo(() => {
    if (step === 1) return Boolean(answers.cefr_level)
    if (step === 2) return Boolean(answers.industry)
    if (step === 3) return answers.interests.length > 0
    if (step === 4) return Boolean(answers.goal)
    if (step === 5) return Boolean(answers.style)
    if (step === 6) return Boolean(answers.time)
    return false
  }, [answers, step])

  const learningGoals = [
    answers.goal,
    ...answers.interests.slice(0, 3).map((interest) => `Chủ đề: ${interest}`),
    answers.style ? `Phong cách: ${answers.style}` : '',
  ].filter(Boolean).slice(0, 10)

  const summary = `Dựa trên thông tin của bạn, Luna sẽ dạy tiếng Anh ${answers.industryLabel || 'theo ngữ cảnh cá nhân'} qua ${answers.style || 'bài học ngắn'} và ưu tiên mục tiêu ${answers.goal || 'giao tiếp thực tế'}.`

  const goNext = async () => {
    if (!canContinue) return
    setError('')
    if (step < totalSteps) {
      setStep((value) => value + 1)
      return
    }

    setSubmitting(true)
    try {
      const payload = {
        email: currentUser?.email || location.state?.email || null,
        display_name: currentUser?.display_name || location.state?.display_name || null,
        cefr_level: answers.cefr_level,
        industry: answers.industry,
        learning_goals: learningGoals,
        preferred_study_time: answers.time || null,
      }

      if (currentUser?.user_id) {
        const updated = await tutorAPI.updateUserPreferences(currentUser.user_id, payload)
        setUser(updated?.user_id ? updated : { ...currentUser, ...payload })
      } else {
        const user = await tutorAPI.onboarding(payload)
        setUser(user)
      }
      setCompleted(true)
    } catch (requestError) {
      setError(getErrorMessage(requestError, 'onboarding.save'))
    } finally {
      setSubmitting(false)
    }
  }

  if (completed) {
    return (
      <div className="page-shell grid min-h-dvh place-items-center px-5 py-6">
        <div className="card max-w-[640px] p-6 text-center sm:p-8">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-[var(--green-soft)] text-4xl text-[var(--green)]">✓</div>
          <h1 className="font-display mt-5 text-[clamp(2.2rem,5vw,3.8rem)] font-semibold leading-none">Gia sư của bạn đã sẵn sàng.</h1>
          <p className="copy-lg mx-auto mt-4 max-w-[560px]">{summary}</p>
          <button className="btn btn-primary mx-auto mt-6 text-xl" onClick={() => navigate('/app', { replace: true })} type="button">
            Bắt đầu học ngay
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="page-shell min-h-dvh">
      <div className="fixed inset-x-0 top-0 z-30 h-1 bg-[var(--cream-3)]">
        <div className="h-full bg-[var(--ochre-bright)] transition-all duration-300" style={{ width: `${progress}%` }} />
      </div>
      <div className="mx-auto grid min-h-dvh w-full max-w-[980px] place-items-center px-4 py-6 sm:px-5 lg:py-8">
        <main className="w-full">
          <div className="mb-6 grid grid-cols-[1fr_auto_1fr] items-center sm:mb-8">
            <p className="text-sm font-semibold tracking-[0.16em] text-[var(--muted)]">Câu hỏi {step}/6</p>
            <Link className="grid h-11 w-11 place-items-center rounded-full bg-[rgba(108,90,75,0.12)] text-2xl text-white" to="/">
              ×
            </Link>
            <Link className="logo justify-self-end !text-[1.75rem]" to="/">Lingo·AI</Link>
          </div>

          <section className="text-center">
            <h1 className="font-display text-[clamp(2rem,4vw,3.2rem)] font-semibold leading-[1.02] tracking-[-0.05em]">{titleForStep(step)}</h1>
            <p className="copy-lg mx-auto mt-3 max-w-[680px]">{subtitleForStep(step)}</p>
          </section>

          <div className="mt-7 sm:mt-9">
            {step === 1 ? <LevelStep selected={answers.cefr_level} onSelect={(cefr_level) => setAnswers((value) => ({ ...value, cefr_level }))} /> : null}
            {step === 2 ? <ChipStep options={occupations} selected={[answers.industry]} onSelect={(item) => setAnswers((value) => ({ ...value, industry: item.value, industryLabel: item.label }))} /> : null}
            {step === 3 ? <InterestStep selected={answers.interests} onToggle={(interest) => toggleInterest(interest, setAnswers)} /> : null}
            {step === 4 ? <GoalStep selected={answers.goal} onSelect={(goal) => setAnswers((value) => ({ ...value, goal }))} /> : null}
            {step === 5 ? <StyleStep selected={answers.style} onSelect={(style) => setAnswers((value) => ({ ...value, style }))} /> : null}
            {step === 6 ? <TimeStep selected={answers.time} onSelect={(time) => setAnswers((value) => ({ ...value, time }))} /> : null}
          </div>

          {error ? <p className="mx-auto mt-8 max-w-[560px] rounded-xl bg-[#fff1eb] px-4 py-3 text-center text-sm text-[var(--red)]">{error}</p> : null}

          <div className="mt-7 flex items-center justify-between gap-4 sm:mt-8">
            <button className="btn btn-ghost !w-auto" disabled={step === 1 || submitting} onClick={() => setStep((value) => Math.max(1, value - 1))} type="button">
              Quay lại
            </button>
            <button className="btn btn-primary !w-auto" disabled={!canContinue || submitting} onClick={goNext} type="button">
              {step === totalSteps ? (submitting ? 'Đang lưu...' : 'Hoàn tất') : 'Tiếp tục'}
            </button>
          </div>
        </main>
      </div>
    </div>
  )
}

function LevelStep({ selected, onSelect }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {levels.map((level) => {
        const Icon = level.icon
        return <OptionCard icon={<Icon />} key={level.value} selected={selected === level.value} text={level.text} title={level.title} onClick={() => onSelect(level.value)} />
      })}
    </div>
  )
}

function ChipStep({ options, selected, onSelect }) {
  return (
    <div className="flex flex-wrap justify-center gap-2.5">
      {options.map((option, index) => (
        <button className={`rounded-full border px-4 py-2.5 ${selected.includes(option.value) ? 'border-[var(--ochre-bright)] bg-[var(--ochre-soft)] text-[var(--ochre)]' : 'border-[var(--line-strong)] bg-white text-[var(--ink)]'}`} key={`${option.label}-${index}`} onClick={() => onSelect(option)} type="button">
          {option.label}
        </button>
      ))}
    </div>
  )
}

function InterestStep({ selected, onToggle }) {
  return (
    <>
      <div className="flex flex-wrap justify-center gap-2.5">
        {interests.map((interest) => (
          <button className={`rounded-full border px-4 py-2.5 ${selected.includes(interest) ? 'border-[var(--ochre-bright)] bg-[var(--ochre-soft)] text-[var(--ochre)]' : 'border-[var(--line-strong)] bg-white text-[var(--ink)]'}`} key={interest} onClick={() => onToggle(interest)} type="button">
            {interest}
          </button>
        ))}
      </div>
      <p className="mt-4 text-center text-sm text-[var(--muted)]">Chọn tối đa 3 chủ đề bạn thích nhất</p>
    </>
  )
}

function GoalStep({ selected, onSelect }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {goals.map((goal) => {
        const Icon = goal.icon
        return <OptionCard horizontal icon={<Icon />} key={goal.value} selected={selected === goal.value} text={goal.text} title={goal.title} onClick={() => onSelect(goal.value)} />
      })}
    </div>
  )
}

function StyleStep({ selected, onSelect }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {styles.map((style) => {
        const Icon = style.icon
        return <OptionCard icon={<Icon />} key={style.value} selected={selected === style.value} title={style.value} onClick={() => onSelect(style.value)} />
      })}
    </div>
  )
}

function TimeStep({ selected, onSelect }) {
  return (
    <div className="flex flex-wrap justify-center gap-2.5">
      {times.map((time) => (
        <button className={`rounded-full border px-5 py-3 text-lg ${selected === time ? 'border-[var(--ochre-bright)] bg-[var(--ochre-soft)] text-[var(--ochre)]' : 'border-[var(--line-strong)] bg-white text-[var(--ink)]'}`} key={time} onClick={() => onSelect(time)} type="button">
          {time}
        </button>
      ))}
    </div>
  )
}

function OptionCard({ horizontal = false, selected, icon, title, text, onClick }) {
  return (
    <button className={`card w-full p-4 text-left transition hover:-translate-y-0.5 sm:p-5 ${horizontal ? 'flex items-start gap-4' : 'min-h-[128px]'} ${selected ? '!border-[var(--ochre-bright)] !bg-[var(--ochre-soft)]' : ''}`} onClick={onClick} type="button">
      <span className="inline-flex text-[var(--ochre)]">{icon}</span>
      <span className={horizontal ? 'block' : ''}>
        <span className={`${horizontal ? 'mt-0' : 'mt-4'} block font-display text-[1.35rem] font-semibold leading-tight`}>{title}</span>
        {text ? <span className="mt-2 block text-sm leading-relaxed text-[var(--muted)]">{text}</span> : null}
      </span>
    </button>
  )
}

function toggleInterest(interest, setAnswers) {
  setAnswers((current) => {
    if (current.interests.includes(interest)) {
      return { ...current, interests: current.interests.filter((item) => item !== interest) }
    }
    if (current.interests.length >= 3) return current
    return { ...current, interests: [...current.interests, interest] }
  })
}

function titleForStep(step) {
  return ['Trình độ hiện tại của bạn là gì?', 'Bạn đang làm trong lĩnh vực nào?', 'Bạn thích học qua chủ đề nào?', 'Mục tiêu học tập chính của bạn là gì?', 'Bạn muốn gia sư dạy theo cách nào?', 'Bạn có thể học bao lâu mỗi ngày?'][step - 1]
}

function subtitleForStep(step) {
  return ['Hãy chọn một mức độ phản ánh đúng nhất khả năng của bạn.', 'Gia sư sẽ dùng thông tin này để cá nhân hóa ví dụ và từ vựng phù hợp.', 'Chọn những chủ đề khiến bạn muốn quay lại học thường xuyên hơn.', 'Chúng tôi sẽ tối ưu giáo án dựa trên mục tiêu gần nhất của bạn.', 'Mỗi người tiếp thu khác nhau. Hãy cho gia sư biết cách bạn thích học.', 'Một lịch học thực tế sẽ giúp việc duy trì tiến độ dễ hơn nhiều.'][step - 1]
}

function IconBase({ children }) {
  return <svg aria-hidden="true" fill="none" height="34" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" viewBox="0 0 24 24" width="34">{children}</svg>
}

function RabbitIcon() { return <IconBase><path d="M9.5 8c-.8-2.2-2-4-3-4-1.3 0-1.6 2.6-.8 5" /><path d="M14.5 8c.8-2.2 2-4 3-4 1.3 0 1.6 2.6.8 5" /><path d="M7 15a5 5 0 1 0 10 0c0-2.8-2.2-5-5-5s-5 2.2-5 5Z" /></IconBase> }
function WalkIcon() { return <IconBase><circle cx="13" cy="5" r="1.5" /><path d="m12 8-2.5 4 2 2.5" /><path d="m12 8 3 2 1.5 5" /><path d="m9.5 12-2 8" /></IconBase> }
function HatIcon() { return <IconBase><path d="m4 10 8-4 8 4-8 4-8-4Z" /><path d="M8 12v3.5c0 1.7 1.8 3 4 3s4-1.3 4-3V12" /></IconBase> }
function RocketIcon() { return <IconBase><path d="M14 4c3 1 5 3 6 6-2.5.5-5.5 2.5-7 5-2.5 1.5-4.5 4.5-5 7-3-1-5-3-6-6 2.5-.5 5.5-2.5 7-5 1.5-2.5 4.5-4.5 7-7Z" /></IconBase> }
function MessageIcon() { return <IconBase><path d="M4 5h16v11H8l-4 4V5Z" /><path d="M8 10h8" /></IconBase> }
function BriefcaseIcon() { return <IconBase><rect height="11" rx="2" width="18" x="3" y="8" /><path d="M8 8V6a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></IconBase> }
function CertificateIcon() { return <IconBase><circle cx="12" cy="9" r="4" /><path d="m10 13-1 7 3-2 3 2-1-7" /></IconBase> }
function PlaneIcon() { return <IconBase><path d="m3 11 18-8-6 18-3-7-9-3Z" /></IconBase> }
function BookIcon() { return <IconBase><path d="M5 5.5A2.5 2.5 0 0 1 7.5 3H19v16H7.5A2.5 2.5 0 0 0 5 21V5.5Z" /></IconBase> }
function BoltIcon() { return <IconBase><path d="M13 2 5 13h5l-1 9 8-11h-5l1-9Z" /></IconBase> }
function BulbIcon() { return <IconBase><path d="M9 18h6" /><path d="M12 2a6 6 0 0 0-3 11.2c.6.4 1 1.1 1 1.8V16h4v-1c0-.7.4-1.4 1-1.8A6 6 0 0 0 12 2Z" /></IconBase> }
function PencilIcon() { return <IconBase><path d="m4 20 4.5-1 9-9a2.1 2.1 0 0 0-3-3l-9 9L4 20Z" /><path d="m13.5 6.5 4 4" /></IconBase> }
