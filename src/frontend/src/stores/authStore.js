import { create } from 'zustand'
import { authAPI } from '../services/api.js'
import { useChatStore } from './chatStore.js'

function clearSessionState() {
  useChatStore.getState().reset()
}

// Cookie (httpOnly) is the source of truth. We hydrate the store by calling
// /auth/me on app boot. We DO NOT persist user JSON in localStorage anymore;
// that was insecure and got out of sync with the cookie.
//
// status: 'idle' | 'loading' | 'authenticated' | 'unauthenticated'
export const useAuthStore = create((set, get) => ({
  user: null,
  status: 'idle',

  setUser: (user) => {
    const previousUserId = get().user?.user_id || null
    const nextUserId = user?.user_id || null
    if (previousUserId !== nextUserId) {
      clearSessionState()
    }
    set({ user, status: user ? 'authenticated' : 'unauthenticated' })
  },

  // Local-only clear (used after a successful logout API call or when a
  // 401 response is observed). Does NOT call the backend.
  clear: () => {
    clearSessionState()
    set({ user: null, status: 'unauthenticated' })
  },

  // Backwards-compat alias kept so existing callers (HomePage, ChatPage,
  // SettingsPage) don't break. Performs the real backend logout then clears.
  logout: async () => {
    try {
      await authAPI.logout()
    } catch {
      // ignore network errors — we still clear locally
    }
    clearSessionState()
    set({ user: null, status: 'unauthenticated' })
  },

  hydrate: async () => {
    if (get().status === 'loading') return
    set({ status: 'loading' })
    try {
      const me = await authAPI.me()
      set({ user: me, status: 'authenticated' })
      return me
    } catch {
      set({ user: null, status: 'unauthenticated' })
      return null
    }
  },
}))
