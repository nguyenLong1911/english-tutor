import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import LoadingSpinner from '../components/common/LoadingSpinner.jsx'
import { adminAPI, getErrorMessage } from '../services/api.js'
import { useAuthStore } from '../stores/authStore.js'

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const USERS_PAGE_SIZE = 10

export default function AdminDashboardPage() {
  const user = useAuthStore((s) => s.user)
  const status = useAuthStore((s) => s.status)
  const navigate = useNavigate()
  const [range, setRange] = useState('30d')
  const [metrics, setMetrics] = useState(null)
  const [users, setUsers] = useState([])
  const [userTotal, setUserTotal] = useState(0)
  const [userPage, setUserPage] = useState(0)
  const [usersLoading, setUsersLoading] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (status === 'unauthenticated') navigate('/auth')
  }, [status, navigate])

  useEffect(() => {
    if (status !== 'authenticated' || !user) return
    if (user.role !== 'admin') {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    adminAPI.dashboard()
      .then((dashboard) => {
        setMetrics(dashboard)
      })
      .catch((err) => setError(getErrorMessage(err, 'admin.load')))
      .finally(() => setLoading(false))
  }, [status, user])

  useEffect(() => {
    if (status !== 'authenticated' || !user || user.role !== 'admin') return
    setUsersLoading(true)
    setError(null)
    adminAPI.users({ limit: USERS_PAGE_SIZE, offset: userPage * USERS_PAGE_SIZE })
      .then((userList) => {
        const total = Number(userList.total || 0)
        setUsers(userList.users || [])
        setUserTotal(total)
        if (total > 0 && userPage > 0 && userPage * USERS_PAGE_SIZE >= total) {
          setUserPage(Math.max(0, Math.ceil(total / USERS_PAGE_SIZE) - 1))
        }
      })
      .catch((err) => setError(getErrorMessage(err, 'admin.load')))
      .finally(() => setUsersLoading(false))
  }, [status, user, userPage])

  const targets = metrics?.targets || {}
  const totalUserPages = Math.max(1, Math.ceil(userTotal / USERS_PAGE_SIZE))
  const userStart = userTotal === 0 ? 0 : userPage * USERS_PAGE_SIZE + 1
  const userEnd = Math.min(userTotal, (userPage + 1) * USERS_PAGE_SIZE)
  const kpis = useMemo(() => ([
    {
      label: 'D7 Retention',
      value: `${formatNumber(metrics?.d7_retention)}%`,
      target: `Target >= ${targets.d7_retention ?? 35}%`,
      progress: percent(metrics?.d7_retention, targets.d7_retention ?? 35),
      tone: 'green',
    },
    {
      label: 'D30 Retention',
      value: `${formatNumber(metrics?.d30_retention)}%`,
      target: `Target >= ${targets.d30_retention ?? 20}%`,
      progress: percent(metrics?.d30_retention, targets.d30_retention ?? 20),
      tone: 'green',
    },
    {
      label: 'Avg Session',
      value: `${formatNumber(metrics?.avg_session_minutes)}m`,
      target: `${targets.avg_session_minutes_min ?? 15}-${targets.avg_session_minutes_max ?? 20} mins`,
      progress: percent(metrics?.avg_session_minutes, targets.avg_session_minutes_min ?? 15),
      tone: 'orange',
    },
    {
      label: 'Token Savings',
      value: `${formatNumber(metrics?.token_savings_percent)}%`,
      target: `Target ${targets.token_savings_percent ?? 90}%`,
      progress: percent(metrics?.token_savings_percent, targets.token_savings_percent ?? 90),
      tone: 'green',
    },
  ]), [metrics, targets])

  if (status !== 'authenticated' || loading) {
    return (
      <div className="app-loading">
        <LoadingSpinner label="Đang tải admin dashboard..." />
      </div>
    )
  }

  if (user?.role !== 'admin') {
    return (
      <div className="page-shell grid min-h-screen place-items-center px-4">
        <section className="w-full max-w-md rounded-[8px] border border-[var(--line)] bg-white p-6 text-center shadow-sm">
          <h1 className="font-display text-2xl text-[var(--ink)]">Không có quyền admin</h1>
          <p className="mt-2 text-sm text-[var(--muted)]">Tài khoản hiện tại chưa được cấp quyền xem dashboard nội bộ.</p>
          <Link className="btn btn-primary mt-5" to="/app">Quay lại ứng dụng</Link>
        </section>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#fff8f4] text-[var(--ink)]">
      <div className="grid min-h-screen lg:grid-cols-[282px_1fr]">
        <AdminSidebar />

        <main className="min-w-0 px-4 py-8 sm:px-8 lg:px-16">
          <header className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
            <div>
              <h1 className="font-display text-2xl text-[var(--ink)]">Admin Dashboard</h1>
              <p className="mt-1 text-[15px] text-[var(--muted)]">Monitoring system performance and user retention.</p>
            </div>
            <div className="inline-flex w-fit rounded-full bg-[#f8eadc] p-1 shadow-sm">
              {['7d', '30d'].map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setRange(item)}
                  className={`min-h-11 rounded-full px-7 text-sm transition ${
                    range === item ? 'bg-[var(--ochre-bright)] text-[var(--ink)] shadow' : 'text-[var(--ink)]'
                  }`}
                >
                  {item === '7d' ? '7 ngày' : '30 ngày'}
                </button>
              ))}
            </div>
          </header>

          {error && (
            <p className="mt-5 rounded-[8px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
          )}

          <section className="mt-10 grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
            {kpis.map((item) => <KpiCard key={item.label} {...item} />)}
          </section>

          <section className="mt-11 grid gap-6 xl:grid-cols-[minmax(0,1fr)_208px]">
            <Panel title="Retention Trends" className="min-h-[442px]">
              <div className="mb-4 flex justify-end gap-5 text-sm">
                <Legend color="#f59b00" label="D7" />
                <Legend color="#315f3f" label="D30" />
              </div>
              <div className="h-[310px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={metrics?.retention_trend || []} margin={{ left: -22, right: 8, top: 8, bottom: 0 }}>
                    <CartesianGrid stroke="#f2e7dc" vertical={false} />
                    <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: '#ead8c7' }} tick={{ fill: '#3b2a20', fontSize: 13 }} />
                    <YAxis hide domain={[0, 100]} />
                    <Tooltip contentStyle={{ borderRadius: 8, borderColor: '#ead8c7' }} />
                    <Line type="monotone" dataKey="d7" stroke="#f59b00" strokeWidth={3} dot={false} />
                    <Line type="monotone" dataKey="d30" stroke="#315f3f" strokeWidth={3} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Panel>

            <Panel title="Mood Check-in Rate" className="min-h-[442px]">
              <div className="mb-4 font-display text-4xl text-[var(--ochre)]">{formatNumber(metrics?.mood_checkin_rate)}%</div>
              <div className="h-[250px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={metrics?.mood_week || []}>
                    <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: '#3b2a20', fontSize: 12 }} />
                    <YAxis hide />
                    <Tooltip cursor={{ fill: '#fff2df' }} contentStyle={{ borderRadius: 8, borderColor: '#ead8c7' }} />
                    <Bar dataKey="value" fill="#bee7c4" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          </section>

          <section className="mt-11 overflow-hidden rounded-[8px] bg-white shadow-[var(--shadow-card)]">
            <div className="flex flex-col gap-3 bg-[#fff0e1] px-7 py-6 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="font-display text-xl">Token Cost Management</h2>
              <button type="button" onClick={downloadCsv} className="inline-flex items-center gap-2 text-sm font-medium text-[var(--ochre)]">
                <span aria-hidden="true">⇩</span> Export CSV
              </button>
            </div>
            <div className="overflow-x-auto">
              <div className="min-w-[980px]">
                <div className="grid grid-cols-[1.45fr_0.85fr_0.9fr_1.4fr_0.75fr_40px] border-b border-[#f0e5db] bg-[#fbf7f3] px-7 py-5 text-xs font-bold uppercase tracking-wide text-[var(--ink)]">
                  <span>User</span>
                  <span>Total Queries</span>
                  <span>Token Cost</span>
                  <span>Trace</span>
                  <span>Status</span>
                  <span className="sr-only">Action</span>
                </div>
                {(users || []).map((item) => <UserRow key={item.user_id} user={item} />)}
              </div>
            </div>
            {users.length === 0 && (
              <div className="px-7 py-8 text-sm text-[var(--muted)]">Chưa có dữ liệu user để hiển thị.</div>
            )}
            <div className="flex flex-col gap-3 bg-[#fff8f1] px-7 py-5 text-sm text-[var(--muted)] sm:flex-row sm:items-center sm:justify-between">
              <span>
                Hiển thị {formatInteger(userStart)}-{formatInteger(userEnd)} / {formatInteger(userTotal)} user
              </span>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  disabled={usersLoading || userPage === 0}
                  onClick={() => setUserPage((page) => Math.max(0, page - 1))}
                  className="min-h-10 rounded-[8px] border border-[var(--line)] bg-white px-4 font-medium text-[var(--ink)] disabled:cursor-not-allowed disabled:opacity-45"
                >
                  Trước
                </button>
                <span className="min-w-[5.5rem] text-center font-medium text-[var(--ink)]">
                  {userPage + 1} / {totalUserPages}
                </span>
                <button
                  type="button"
                  disabled={usersLoading || userPage + 1 >= totalUserPages}
                  onClick={() => setUserPage((page) => Math.min(totalUserPages - 1, page + 1))}
                  className="min-h-10 rounded-[8px] border border-[var(--line)] bg-white px-4 font-medium text-[var(--ink)] disabled:cursor-not-allowed disabled:opacity-45"
                >
                  Sau
                </button>
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}

function AdminSidebar() {
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/auth', { replace: true })
  }

  return (
    <aside className="hidden border-r border-[#f0dfce] bg-[#fff0e1] px-4 py-12 lg:flex lg:flex-col">
      <div className="px-3">
        <p className="font-display text-lg text-[var(--ochre)]">Lingo·AI</p>
        <p className="mt-1 text-sm text-[var(--ink)]">Scholar Tier Admin</p>
      </div>
      <nav className="mt-10 space-y-3">
        <SidebarItem active icon="▦" label="Progress" />
      </nav>
      <div className="mt-auto border-t border-[#e8d4c2] pt-9">
        <SidebarItem icon="⚙" label="Settings" />
        <SidebarItem icon="?" label="Help" />
        <button
          type="button"
          onClick={handleLogout}
          className="mt-6 flex min-h-14 w-full items-center gap-5 rounded-[8px] px-5 text-left text-sm text-[var(--red)] transition hover:bg-white"
        >
          <span className="w-5 text-center text-lg" aria-hidden="true">↩</span>
          <span>Đăng xuất</span>
        </button>
      </div>
    </aside>
  )
}

function SidebarItem({ active = false, icon, label }) {
  return (
    <div className={`flex min-h-14 items-center gap-5 rounded-[8px] px-5 text-sm ${active ? 'bg-[var(--ochre-bright)]' : ''}`}>
      <span className="w-5 text-center text-lg" aria-hidden="true">{icon}</span>
      <span>{label}</span>
    </div>
  )
}

function KpiCard({ label, value, target, progress, tone }) {
  const color = tone === 'orange' ? '#f59b00' : '#315f3f'
  return (
    <article className="rounded-[8px] border-t-2 border-[var(--ochre-bright)] bg-white px-7 py-8 shadow-[var(--shadow-card)]">
      <div className="flex items-start justify-between gap-4">
        <h2 className="max-w-[7rem] text-[15px] uppercase leading-7 tracking-wide">{label}</h2>
        <p className="text-sm font-bold text-[#315f3f]">{target}</p>
      </div>
      <p className="mt-5 font-display text-2xl">{value}</p>
      <div className="mt-3 h-1 rounded-full bg-[#eadfD5]">
        <div className="h-1 rounded-full" style={{ width: `${progress}%`, backgroundColor: color }} />
      </div>
    </article>
  )
}

function Panel({ title, className = '', children }) {
  return (
    <section className={`rounded-[8px] bg-white p-7 shadow-[var(--shadow-card)] ${className}`}>
      <h2 className="font-display text-xl">{title}</h2>
      {children}
    </section>
  )
}

function Legend({ color, label }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  )
}

function UserRow({ user }) {
  const initials = initialsFor(user)
  const overLimit = user.status === 'over_limit'
  const trace = user.trace || {}
  const traceLabel = [trace.provider, trace.model].filter(Boolean).join(' · ') || 'No LLM trace'
  const traceDetail = `${formatInteger(trace.total_tokens)} tokens · ${formatInteger(trace.latency_ms)}ms`
  return (
    <div className="grid min-h-[120px] grid-cols-[1.45fr_0.85fr_0.9fr_1.4fr_0.75fr_40px] items-center border-b border-[#f4ebe4] px-7 py-5 text-sm">
      <div className="flex items-center gap-4">
        <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-full font-bold ${overLimit ? 'bg-[#ffd8c6]' : 'bg-[#cdeecf]'}`}>
          {initials}
        </div>
        <div>
          <p className="font-medium">{user.display_name || nameFromEmail(user.email)}</p>
          <p className="mt-1 text-xs text-[var(--muted)]">ID: #{String(user.user_id || '').slice(0, 5)}</p>
        </div>
      </div>
      <p>{formatInteger(user.queries ?? user.sessions)} queries</p>
      <p className={overLimit ? 'font-bold text-red-600' : ''}>{formatCost(user.cost_usd)}</p>
      <div className="min-w-0">
        <p className="truncate font-medium">{traceLabel}</p>
        <p className="mt-1 text-xs text-[var(--muted)]">{traceDetail}</p>
      </div>
      <span className={`w-fit rounded-full px-4 py-2 text-xs font-bold ${overLimit ? 'bg-[#ffd8d4] text-red-700' : 'bg-[#c9ebca] text-[#315f3f]'}`}>
        {overLimit ? 'Over Limit' : 'Stable'}
      </span>
      <button type="button" aria-label={`Actions for ${user.email || user.user_id}`} className="text-xl leading-none">⋮</button>
    </div>
  )
}

function downloadCsv() {
  adminAPI.exportCsv().then((blob) => {
    const href = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = href
    anchor.download = 'admin_dashboard.csv'
    anchor.click()
    URL.revokeObjectURL(href)
  })
}

function percent(value, target) {
  if (!target) return 0
  return Math.max(0, Math.min(100, (Number(value || 0) / Number(target)) * 100))
}

function formatNumber(value) {
  const n = Number(value || 0)
  return Number.isInteger(n) ? String(n) : n.toFixed(1)
}

function formatInteger(value) {
  return new Intl.NumberFormat('en-US').format(Number(value || 0))
}

function formatCost(value) {
  const n = Number(value || 0)
  if (n === 0) return money.format(0)
  if (Math.abs(n) < 0.01) return `$${n.toFixed(6)}`
  return money.format(n)
}

function nameFromEmail(email) {
  if (!email) return 'Anonymous User'
  return email.split('@')[0].replace(/[._-]+/g, ' ')
}

function initialsFor(user) {
  const source = user.display_name || nameFromEmail(user.email)
  const initials = source.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('')
  return (initials || 'U').toUpperCase()
}
