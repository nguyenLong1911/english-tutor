import { create } from 'zustand'

export const useChatStore = create((set, get) => ({
  ownerUserId: null,
  messages: [],
  appendMessage: (msg, ownerUserId = get().ownerUserId) =>
    set({ messages: [...get().messages, msg], ownerUserId }),
  setMessages: (messages, ownerUserId = get().ownerUserId) => set({ messages, ownerUserId }),
  bindUser: (userId) => {
    if (get().ownerUserId === userId) return
    set({ ownerUserId: userId, messages: [] })
  },
  reset: (ownerUserId = null) => set({ messages: [], ownerUserId }),
}))
