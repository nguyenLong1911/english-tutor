import { useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore.js'

export default function BottomNav() {
  const location = useLocation()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)

  // Don't show nav on home or onboarding pages
  if (!user || ['/onboarding', '/', '/chat'].includes(location.pathname)) {
    return null
  }

  const navItems = [
    { path: '/chat', icon: '💬', label: 'Chat', ariaLabel: 'Trang Chat' },
    { path: '/review', icon: '📝', label: 'Ôn tập', ariaLabel: 'Trang Ôn tập từ vựng' },
    { path: '/dashboard', icon: '📊', label: 'Báo cáo', ariaLabel: 'Bảng điều khiển tiến độ' },
    { path: '/settings', icon: '⚙️', label: 'Cài đặt', ariaLabel: 'Cài đặt người dùng' },
  ]

  const handleKeyDown = (e, path) => {
    // Allow Enter and Space to activate navigation
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      navigate(path)
    }
  }

  return (
    <nav 
      className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg dark:border-slate-800 dark:bg-slate-900"
      role="navigation"
      aria-label="Điều hướng chính"
    >
      <div className="flex justify-around">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              onKeyDown={(e) => handleKeyDown(e, item.path)}
              aria-label={item.ariaLabel}
              aria-current={isActive ? 'page' : undefined}
              className={`flex-1 flex flex-col items-center justify-center py-3 px-2 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset ${
                isActive
                  ? 'bg-blue-50 text-blue-600 border-t-2 border-blue-600 dark:bg-sky-950 dark:text-sky-300'
                  : 'text-gray-600 hover:bg-gray-50 dark:text-slate-300 dark:hover:bg-slate-800'
              }`}
              title={item.label}
            >
              <span className="text-2xl" aria-hidden="true">{item.icon}</span>
              <span className="text-xs mt-1 font-medium">{item.label}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
