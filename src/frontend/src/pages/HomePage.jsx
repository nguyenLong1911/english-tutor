import { Link } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore.js'

const features = [
  {
    icon: MessageIcon,
    title: 'Học qua chat',
    description:
      'Tương tác tự nhiên như đang nhắn tin với một người bạn bản xứ. Không còn những bài học khô khan.',
  },
  {
    icon: UserIcon,
    title: 'Ghi nhớ cá nhân',
    description:
      'AI ghi nhớ sở thích, mục tiêu và điểm yếu của bạn để điều chỉnh nội dung bài học mỗi ngày.',
  },
  {
    icon: BrainIcon,
    title: 'Ghi nhớ lỗi',
    description:
      'Mọi lỗi sai đều được lưu lại và tự động tạo thành bài ôn tập ngắn để bạn không mắc lại.',
  },
  {
    icon: RefreshIcon,
    title: 'Nhắc lại gián đoạn',
    description:
      'Spaced repetition đảm bảo từ vựng được ôn lại đúng thời điểm bạn sắp quên.',
  },
]

const workflow = [
  {
    step: '1',
    title: 'Học bài giảng',
    description: 'Tiếp thu kiến thức mới thông qua các đoạn hội thoại ngắn, tập trung vào ngữ cảnh thực tế.',
  },
  {
    step: '2',
    title: 'Ôn tập',
    description: 'Thực hành ngay lập tức với gia sư AI, nhận phản hồi và sửa lỗi trực tiếp trong khi luyện nói.',
  },
  {
    step: '3',
    title: 'Flashcard',
    description: 'Củng cố trí nhớ dài hạn bằng hệ thống thẻ từ vựng thông minh, tập trung vào những từ bạn hay quên.',
  },
]

export default function HomePage() {
  const user = useAuthStore((s) => s.user)
  const status = useAuthStore((s) => s.status)
  const primaryHref = status === 'authenticated' ? '/app' : '/auth'

  return (
    <div className="page-shell">
      <header className="sticky top-0 z-30 border-b border-[var(--line)] bg-[rgba(255,250,247,0.88)] backdrop-blur">
        <div className="container-xl flex min-h-[72px] items-center justify-between gap-5 lg:min-h-[82px]">
          <Link className="logo" to="/">
            Lingo·AI
          </Link>
          <nav className="hidden items-center gap-12 text-[17px] text-[var(--muted)] md:flex">
            <a href="#methodology">Methodology</a>
            <a href="#pricing">Pricing</a>
            <a href="#about">About</a>
          </nav>
          <div className="flex items-center gap-3">
            <Link className="btn btn-ghost !hidden sm:!inline-flex" to={user ? '/app' : '/auth'}>
              {user ? 'Vào lớp học' : 'Đăng nhập'}
            </Link>
            <Link className="btn btn-primary shrink-0 whitespace-nowrap" to={primaryHref}>
              Bắt đầu miễn phí
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="container-xl grid min-h-[calc(100dvh-82px)] items-center gap-10 py-10 lg:grid-cols-[1.05fr_0.95fr] lg:gap-12 lg:py-12">
          <div>
            <div className="eyebrow fade-up">
              <ChipIcon />
              Gia sư AI · Trí nhớ dài hạn
            </div>
            <h1 className="title-display mt-6 max-w-[720px] fade-up [animation-delay:80ms]">
              Học tiếng Anh với gia sư nhớ <span className="text-[var(--ochre)]">mọi thứ</span> về bạn.
            </h1>
            <p className="mt-5 max-w-[560px] font-display text-[1.45rem] font-semibold leading-tight text-[var(--muted)] fade-up [animation-delay:140ms] sm:text-[1.6rem]">
              Không phải app học từ vựng...
            </p>
            <p className="copy-lg mt-4 max-w-[620px] fade-up [animation-delay:180ms]">
              Đây là gia sư cá nhân hóa hiểu nghề nghiệp, sở thích và lỗi lầm của bạn, rồi dạy theo cách chỉ dành cho bạn.
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <Link className="btn btn-primary w-full sm:w-auto font-display text-[1.45rem] sm:text-[1.65rem]" to={primaryHref}>
                Bắt đầu miễn phí
              </Link>
              <a className="btn btn-ghost w-full sm:w-auto font-display text-[1.25rem] sm:text-[1.4rem]" href="#demo">
                <PlayIcon />
                Xem demo
              </a>
            </div>
          </div>

          <div id="demo" className="relative">
            <div className="card rounded-b-[18px] rounded-t-none bg-white p-5 shadow-[var(--shadow-float)] sm:p-6">
              <div className="flex items-center gap-4 border-b border-[var(--line-strong)] pb-4">
                <div className="grid h-12 w-12 place-items-center rounded-full bg-[var(--cream-2)] text-[var(--ochre)]">
                  <TutorIcon />
                </div>
                <div>
                  <h2 className="font-display text-3xl font-semibold leading-none">Lingo Tutor</h2>
                  <p className="mt-1 text-[var(--muted)]">Trực tuyến</p>
                </div>
              </div>
              <div className="mt-4 space-y-3 text-[1rem] leading-relaxed">
                <div className="max-w-[86%] rounded-[18px] border border-[var(--line-strong)] bg-[var(--cream-2)] p-3.5">
                  Chào bạn! Mình nhớ hôm qua bạn đang luyện tập về thì quá khứ đơn, đặc biệt là các động từ bất quy tắc.
                </div>
                <div className="ml-auto max-w-[78%] rounded-[18px_18px_4px_18px] bg-[var(--ochre)] p-3.5 text-[#fff9ef]">
                  Chắc chắn rồi. Mình vẫn hay quên từ "teach".
                </div>
                <div className="max-w-[88%] rounded-[18px] border border-[var(--line-strong)] bg-[var(--cream-2)] p-3.5">
                  Không sao, nhiều người cũng vậy. Quá khứ của "teach" là <span className="text-[var(--green)]">taught</span>.
                  Thử đặt một câu với nó xem sao?
                </div>
              </div>
              <div className="mx-auto mt-4 w-max rounded-full border border-[#bfd5bc] bg-[var(--green-soft)] px-4 py-2 text-sm text-[var(--green)]">
                Đã ghi nhớ: Khó khăn với "teach"
              </div>
            </div>
          </div>
        </section>

        <section id="methodology" className="border-y border-[var(--line)] py-20">
          <div className="container-xl">
            <div className="mx-auto max-w-[760px] text-center">
              <h2 className="title-section">Công nghệ cá nhân hóa việc học</h2>
              <p className="copy-lg mt-5">
                Hệ thống AI của Lingo không chỉ dạy, mà còn học cách bạn học để tối ưu hóa quá trình tiếp thu.
              </p>
            </div>
            <div className="mt-12 grid gap-6 md:grid-cols-2 xl:grid-cols-4">
              {features.map((feature) => {
                const Icon = feature.icon
                return (
                  <article className="card min-h-[330px] p-7 transition hover:-translate-y-1 hover:border-[var(--ochre)]" key={feature.title}>
                    <div className="grid h-14 w-14 place-items-center rounded-xl bg-[var(--cream-2)]">
                      <Icon />
                    </div>
                    <h3 className="font-display mt-8 text-[2.25rem] font-semibold leading-none">{feature.title}</h3>
                    <p className="mt-5 text-[1.12rem] leading-relaxed text-[var(--muted)]">{feature.description}</p>
                  </article>
                )
              })}
            </div>
          </div>
        </section>

        <section className="bg-[var(--cream-2)] py-20">
          <div className="container-xl">
            <div className="text-center">
              <h2 className="title-section">Lộ trình học tối giản</h2>
              <p className="copy-lg mt-4">Ba bước đơn giản để xây dựng phản xạ tiếng Anh tự nhiên.</p>
            </div>
            <div className="mt-12 grid gap-10 lg:grid-cols-3">
              {workflow.map((item) => (
                <article className="card relative min-h-[260px] p-9 text-center" key={item.step}>
                  <div className="mx-auto grid h-20 w-20 place-items-center rounded-full border border-[var(--ochre)] bg-[var(--cream-2)] font-display text-4xl font-semibold text-[var(--ochre)]">
                    {item.step}
                  </div>
                  <h3 className="font-display mt-7 text-[2.5rem] font-semibold leading-none">{item.title}</h3>
                  <p className="mt-5 text-lg leading-relaxed text-[var(--muted)]">{item.description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="about" className="container-xl py-24 text-center">
          <div className="mx-auto max-w-[760px]">
            <div className="font-display text-8xl leading-none text-[var(--line-strong)]">"</div>
            <blockquote className="font-display text-[clamp(2rem,4vw,4rem)] font-semibold leading-tight">
              Lingo không chỉ sửa lỗi ngữ pháp, nó nhớ rằng tôi thích nhiếp ảnh và luôn đưa ra các ví dụ từ vựng liên quan đến máy ảnh.
            </blockquote>
            <div className="mt-10 flex items-center justify-center gap-5">
              <div className="h-16 w-16 rounded-full border border-[var(--line-strong)] bg-[var(--cream-2)]" />
              <div className="text-left">
                <p className="font-display text-3xl font-semibold">Minh Tuấn</p>
                <p className="text-[var(--muted)]">Học viên Scholar Tier</p>
              </div>
            </div>
          </div>
        </section>

        <section id="pricing" className="container-xl pb-20">
          <div className="card bg-[var(--cream-2)] px-6 py-20 text-center">
            <h2 className="title-section">Sẵn sàng nâng cao trình độ?</h2>
            <p className="copy-lg mx-auto mt-6 max-w-[760px] font-display text-3xl font-semibold">
              Trải nghiệm phương pháp học tập cá nhân hóa với gia sư AI ghi nhớ mọi thứ về bạn.
            </p>
            <Link className="btn btn-primary mt-10 w-full sm:w-auto font-display text-3xl" to={primaryHref}>
              Tạo tài khoản miễn phí
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-[var(--line)] bg-white py-12">
        <div className="container-xl flex flex-col gap-6 text-[var(--muted)] md:flex-row md:items-center md:justify-between">
          <p className="font-display text-2xl font-semibold text-[var(--ochre)]">© 2024 Lingo·AI. Scholarly Excellence.</p>
          <div className="flex gap-8">
            <a href="#privacy">Privacy</a>
            <a href="#terms">Terms</a>
            <a href="#support">Support</a>
            <a href="#careers">Careers</a>
          </div>
        </div>
      </footer>
    </div>
  )
}

function IconBase({ children }) {
  return (
    <svg aria-hidden="true" fill="none" height="24" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.9" viewBox="0 0 24 24" width="24">
      {children}
    </svg>
  )
}

function MessageIcon() {
  return <IconBase><path d="M4 5h16v11H8l-4 4V5Z" /><path d="M8 9h8" /><path d="M8 13h5" /></IconBase>
}

function UserIcon() {
  return <IconBase><circle cx="12" cy="8" r="4" /><path d="M5 21a7 7 0 0 1 14 0" /></IconBase>
}

function BrainIcon() {
  return <IconBase><path d="M9 5a3 3 0 0 0-4 4 3 3 0 0 0 1 5 4 4 0 0 0 4 5" /><path d="M15 5a3 3 0 0 1 4 4 3 3 0 0 1-1 5 4 4 0 0 1-4 5" /><path d="M12 5v14" /></IconBase>
}

function RefreshIcon() {
  return <IconBase><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 4v7h-7" /></IconBase>
}

function ChipIcon() {
  return <IconBase><rect height="14" rx="2" width="14" x="5" y="5" /><path d="M9 1v4" /><path d="M15 1v4" /><path d="M9 19v4" /><path d="M15 19v4" /></IconBase>
}

function PlayIcon() {
  return <IconBase><circle cx="12" cy="12" r="10" /><path d="m10 8 6 4-6 4V8Z" /></IconBase>
}

function TutorIcon() {
  return <IconBase><path d="m4 10 8-4 8 4-8 4-8-4Z" /><path d="M8 12v4c0 1.5 1.8 2.6 4 2.6s4-1.1 4-2.6v-4" /></IconBase>
}
