import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authAPI, getErrorMessage } from '../services/api.js'
import { useAuthStore } from '../stores/authStore.js'
import { getPostAuthPath } from '../utils/routing.js'

const signupDefaults = {
  display_name: '',
  email: '',
  password: '',
}

const loginDefaults = {
  email: '',
  password: '',
}

export default function AuthPage() {
  const navigate = useNavigate()
  const setUser = useAuthStore((s) => s.setUser)
  const [tab, setTab] = useState('login')
  const [signup, setSignup] = useState(signupDefaults)
  const [login, setLogin] = useState(loginDefaults)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const strength = useMemo(() => {
    const value = signup.password
    let score = 0
    if (value.length >= 8) score += 1
    if (/[A-Z]/.test(value)) score += 1
    if (/[0-9]/.test(value)) score += 1
    if (/[^A-Za-z0-9]/.test(value)) score += 1
    return score
  }, [signup.password])

  const submitLogin = async (event) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const user = await authAPI.login(login.email, login.password)
      setUser(user)
      navigate(getPostAuthPath(user), { replace: true })
    } catch (requestError) {
      setError(getErrorMessage(requestError, 'auth.login'))
    } finally {
      setSubmitting(false)
    }
  }

  const submitSignup = async (event) => {
    event.preventDefault()
    setError('')
    if (signup.password.length < 8) {
      setError('Mật khẩu cần ít nhất 8 ký tự.')
      return
    }

    setSubmitting(true)
    try {
      const user = await authAPI.register({
        ...signup,
        cefr_level: 'B1',
        industry: 'general',
        learning_goals: ['Giao tiếp hàng ngày'],
      })
      setUser(user)
      navigate('/onboarding', {
        replace: true,
        state: { registeredUser: user },
      })
    } catch (requestError) {
      setError(getErrorMessage(requestError, 'auth.signup'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-dvh bg-white text-[var(--ink)]">
      <div className="grid min-h-dvh lg:grid-cols-[45%_55%]">
        <aside className="hidden bg-[var(--cream-2)] lg:block">
          <div className="flex h-full flex-col justify-between px-[7.5vw] py-12 xl:py-16">
            <Link className="logo" to="/">
              Lingo·AI
            </Link>
            <div>
              <h1 className="font-display text-[clamp(3.3rem,4.7vw,5.4rem)] font-semibold leading-[0.94] tracking-[-0.07em]">
                Master languages with absolute focus.
              </h1>
              <p className="mt-6 max-w-[520px] text-xl leading-relaxed text-[var(--muted)] xl:text-2xl">
                A trustworthy AI companion designed for scholarly excellence and uninterrupted study.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-3 text-sm text-[var(--muted)]">
              <span>Trí nhớ dài hạn</span>
              <span>3 hình thức học</span>
              <span>Cá nhân hóa</span>
            </div>
          </div>
        </aside>

        <main className="grid place-items-center px-5 py-6 sm:px-6 lg:py-8">
          <div className="w-full max-w-[560px]">
            <Link className="logo mb-7 block lg:hidden" to="/">
              Lingo·AI
            </Link>

            <div className="grid grid-cols-2 border-b border-[var(--line)]">
              <button className={`pb-3 font-display text-2xl font-semibold sm:text-3xl ${tab === 'login' ? 'border-b-2 border-[var(--ochre)] text-[var(--ochre)]' : 'text-[var(--muted)]'}`} type="button" onClick={() => setTab('login')}>
                Đăng nhập
              </button>
              <button className={`pb-3 font-display text-2xl font-semibold sm:text-3xl ${tab === 'signup' ? 'border-b-2 border-[var(--ochre)] text-[var(--ochre)]' : 'text-[var(--muted)]'}`} type="button" onClick={() => setTab('signup')}>
                Đăng ký
              </button>
            </div>

            {tab === 'login' ? (
              <form className="mt-7 space-y-4 sm:space-y-5" onSubmit={submitLogin}>
                <Field
                  icon={<MailIcon />}
                  label="Email"
                  onChange={(value) => setLogin((current) => ({ ...current, email: value }))}
                  placeholder="name@example.com"
                  type="email"
                  value={login.email}
                />
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <label className="text-[var(--muted)]" htmlFor="login-password">Password</label>
                    <button className="text-sm font-semibold text-[var(--ochre)]" type="button">Forgot?</button>
                  </div>
                  <Field
                    icon={<LockIcon />}
                    id="login-password"
                    onChange={(value) => setLogin((current) => ({ ...current, password: value }))}
                    placeholder="••••••••"
                    trailing={<button className="text-sm text-[var(--ochre)]" onClick={() => setShowPassword((v) => !v)} type="button">{showPassword ? 'Ẩn' : 'Hiện'}</button>}
                    type={showPassword ? 'text' : 'password'}
                    value={login.password}
                  />
                </div>

                <ErrorMessage error={error} />
                <button className="btn btn-primary w-full text-lg" disabled={submitting} type="submit">
                  {submitting ? 'Đang đăng nhập...' : 'Đăng nhập'}
                </button>
                <Divider />
                <a className="btn btn-ghost w-full" href={authAPI.googleStartUrl()}>
                  <span className="grid h-6 w-6 place-items-center bg-black text-xs text-white">G</span>
                  Đăng nhập với Google
                </a>
              </form>
            ) : (
              <form className="mt-7 space-y-4 sm:space-y-5" onSubmit={submitSignup}>
                <Field
                  label="Họ và tên"
                  onChange={(value) => setSignup((current) => ({ ...current, display_name: value }))}
                  placeholder="Nguyễn Văn A"
                  type="text"
                  value={signup.display_name}
                />
                <Field
                  icon={<MailIcon />}
                  label="Email"
                  onChange={(value) => setSignup((current) => ({ ...current, email: value }))}
                  placeholder="name@example.com"
                  type="email"
                  value={signup.email}
                />
                <div>
                  <label className="mb-2 block text-[var(--muted)]" htmlFor="signup-password">Mật khẩu</label>
                  <Field
                    icon={<LockIcon />}
                    id="signup-password"
                    onChange={(value) => setSignup((current) => ({ ...current, password: value }))}
                    placeholder="Tạo mật khẩu"
                    trailing={<button className="text-sm text-[var(--ochre)]" onClick={() => setShowPassword((v) => !v)} type="button">{showPassword ? 'Ẩn' : 'Hiện'}</button>}
                    type={showPassword ? 'text' : 'password'}
                    value={signup.password}
                  />
                  <div className="mt-3 grid grid-cols-4 gap-2">
                    {Array.from({ length: 4 }).map((_, index) => (
                      <span className={`h-1.5 rounded-full ${index < strength ? 'bg-[var(--green)]' : 'bg-[var(--cream-3)]'}`} key={index} />
                    ))}
                  </div>
                </div>

                <ErrorMessage error={error} />
                <button className="btn btn-primary w-full text-lg" disabled={submitting} type="submit">
                  {submitting ? 'Đang tạo...' : 'Tạo tài khoản'}
                </button>
                <Divider />
                <a className="btn btn-ghost w-full" href={authAPI.googleStartUrl()}>
                  <span className="grid h-6 w-6 place-items-center bg-black text-xs text-white">G</span>
                  Tiếp tục với Google
                </a>
                <p className="text-center text-sm leading-6 text-[var(--muted-soft)]">
                  Bằng việc tạo tài khoản, bạn đồng ý để Lingo cá nhân hóa nội dung học theo mục tiêu và tiến độ của bạn.
                </p>
              </form>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}

function Field({ id, label, icon, trailing, type, value, placeholder, onChange }) {
  return (
    <label className="block" htmlFor={id || label}>
      {label ? <span className="mb-2 block text-[var(--muted)]">{label}</span> : null}
      <span className="flex min-h-[50px] items-center gap-4 rounded-[14px] border border-[var(--line-strong)] bg-white px-4 focus-within:border-[var(--ochre)] focus-within:ring-4 focus-within:ring-[rgba(154,98,0,0.09)]">
        {icon ? <span className="text-[var(--muted)]">{icon}</span> : null}
        <input
          className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-[var(--muted-soft)] sm:text-lg"
          id={id || label}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          required
          type={type}
          value={value}
        />
        {trailing}
      </span>
    </label>
  )
}

function Divider() {
  return (
    <div className="flex items-center gap-4 text-[var(--muted)]">
      <span className="h-px flex-1 bg-[var(--line)]" />
      hoặc
      <span className="h-px flex-1 bg-[var(--line)]" />
    </div>
  )
}

function ErrorMessage({ error }) {
  return error ? <p className="rounded-xl bg-[#fff1eb] px-4 py-3 text-sm text-[var(--red)]">{error}</p> : null
}

function IconBase({ children }) {
  return <svg aria-hidden="true" fill="none" height="24" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" viewBox="0 0 24 24" width="24">{children}</svg>
}

function MailIcon() {
  return <IconBase><rect height="16" rx="2" width="20" x="2" y="4" /><path d="m4 7 8 6 8-6" /></IconBase>
}

function LockIcon() {
  return <IconBase><rect height="11" rx="2" width="16" x="4" y="10" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></IconBase>
}
