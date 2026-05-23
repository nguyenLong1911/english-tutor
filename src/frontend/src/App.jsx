import { useEffect, useRef, useState, Suspense, lazy } from 'react'
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import { useAuthStore } from './stores/authStore.js'
import { useThemeStore } from './stores/themeStore.js'
import { authAPI, getErrorMessage } from './services/api.js'
import LoadingSpinner from './components/common/LoadingSpinner.jsx'
import ErrorBoundary from './components/common/ErrorBoundary.jsx'
import { getPostAuthPath, isOnboardingComplete } from './utils/routing.js'

const HomePage = lazy(() => import('./pages/HomePage.jsx'))
const AuthPage = lazy(() => import('./pages/AuthPage.jsx'))
const OnboardingPage = lazy(() => import('./pages/OnboardingPage.jsx'))
const ChatPage = lazy(() => import('./pages/ChatPage.jsx'))
const DashboardPage = lazy(() => import('./pages/DashboardPage.jsx'))
const AdminDashboardPage = lazy(() => import('./pages/AdminDashboardPage.jsx'))
const ReviewPage = lazy(() => import('./pages/ReviewPage.jsx'))
const SettingsPage = lazy(() => import('./pages/SettingsPage.jsx'))
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage.jsx'))
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage.jsx'))

// Intercepts `?code=&state=` from Google OAuth on ANY route (the configured
// redirect_uri is `/app`, but Google could also bounce to `/`). Must live
// inside <BrowserRouter> so it can use the router hooks. Returns null —
// purely a side-effect component rendered alongside <Routes>.
function GoogleOAuthCallbackHandler({ onError }) {
  const navigate = useNavigate()
  const location = useLocation()
  const hydrate = useAuthStore((s) => s.hydrate)
  const ranRef = useRef(false)

  useEffect(() => {
    if (ranRef.current) return
    const params = new URLSearchParams(location.search)
    const code = params.get('code')
    const state = params.get('state')
    const err = params.get('error')
    if (err) {
      ranRef.current = true
      onError(err === 'access_denied' ? 'Bạn đã hủy đăng nhập Google.' : 'Đăng nhập Google chưa hoàn tất. Vui lòng thử lại.')
      navigate(location.pathname, { replace: true })
      return
    }
    if (!code || !state) return
    ranRef.current = true
    ;(async () => {
      try {
        await authAPI.googleCallback(code, state)
        const user = await hydrate()
        navigate(getPostAuthPath(user), { replace: true })
      } catch (e) {
        onError(getErrorMessage(e, 'auth.google'))
        navigate(location.pathname, { replace: true })
      }
    })()
  }, [location.search, location.pathname, navigate, hydrate, onError])

  return null
}

function ProtectedRoute({ children }) {
  const status = useAuthStore((s) => s.status)
  const location = useLocation()

  // Don't redirect while a Google OAuth callback is in flight — the handler
  // mounted at <App> needs to read `?code=&state=` from this URL first.
  const hasOAuthParams = (() => {
    const p = new URLSearchParams(location.search)
    return p.has('code') && p.has('state')
  })()

  if (status === 'idle' || status === 'loading' || hasOAuthParams) {
    return (
      <div className="app-loading">
        <LoadingSpinner label="Đang kiểm tra phiên..." />
      </div>
    )
  }

  if (status !== 'authenticated') {
    return <Navigate to="/auth" replace />
  }

  return children
}

function LearnerRoute({ children }) {
  const user = useAuthStore((s) => s.user)

  if (user?.role === 'admin') {
    return <Navigate to="/admin" replace />
  }

  if (!isOnboardingComplete(user)) {
    return <Navigate to="/onboarding" replace />
  }

  return children
}

export default function App() {
  const theme = useThemeStore((s) => s.theme)
  const hydrate = useAuthStore((s) => s.hydrate)
  const [oauthError, setOauthError] = useState(null)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  // Hydrate auth state from /auth/me once on app boot.
  useEffect(() => {
    hydrate()
  }, [hydrate])

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <GoogleOAuthCallbackHandler onError={setOauthError} />
        {oauthError && (
          <div className="border-b border-red-300 bg-red-50 px-4 py-2 text-center text-sm text-red-700">
            Lỗi đăng nhập Google: {oauthError}
            <button
              type="button"
              onClick={() => setOauthError(null)}
              className="ml-3 underline"
            >
              đóng
            </button>
          </div>
        )}
        <main className="contents">
          <Suspense fallback={<PageLoadingSpinner />}>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/auth" element={<AuthPage />} />
              <Route path="/login" element={<Navigate to="/auth" replace />} />
              <Route path="/onboarding" element={<OnboardingPage />} />
              <Route
                path="/app"
                element={
                  <ProtectedRoute>
                    <LearnerRoute>
                      <ChatPage />
                    </LearnerRoute>
                  </ProtectedRoute>
                }
              />
              <Route path="/chat" element={<Navigate to="/app" replace />} />
              <Route
                path="/dashboard"
                element={<ProtectedRoute><DashboardPage /></ProtectedRoute>}
              />
              <Route
                path="/admin"
                element={<ProtectedRoute><AdminDashboardPage /></ProtectedRoute>}
              />
              <Route
                path="/review"
                element={<ProtectedRoute><ReviewPage /></ProtectedRoute>}
              />
              <Route
                path="/settings"
                element={<ProtectedRoute><SettingsPage /></ProtectedRoute>}
              />
              <Route path="/auth/forgot" element={<ForgotPasswordPage />} />
              <Route path="/auth/reset" element={<ResetPasswordPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </main>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

function PageLoadingSpinner() {
  return (
    <div className="app-loading">
      <LoadingSpinner label="Đang tải trang..." />
    </div>
  )
}
