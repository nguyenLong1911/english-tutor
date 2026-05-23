import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { moodAPI } from '../services/api.js'

// Mood-Adaptive Sessions (§9.1).
// Tracks the latest user mood + derived session config so the chat page can
// render warm prompts and the BE chat call can pass mood_state along.
export const useMoodStore = create(
  persist(
    (set, get) => ({
      mood: null,
      derivedConfig: null,
      checkedAt: null,
      askedAt: null,

      setMood: async (mood) => {
        try {
          const data = await moodAPI.set(mood)
          set({ mood: data.mood, derivedConfig: data.derived_config, checkedAt: Date.now() })
        } catch {
          set({ mood, derivedConfig: null, checkedAt: Date.now() })
        }
      },

      hydrate: async () => {
        try {
          const data = await moodAPI.today()
          set({ mood: data.mood || null, derivedConfig: data.derived_config || null })
        } catch {
          /* not authenticated yet; ignore */
        }
      },

      shouldAsk: () => {
        const { checkedAt, askedAt } = get()
        const last = Math.max(checkedAt || 0, askedAt || 0)
        return Date.now() - last > 1000 * 60 * 60 * 8 // every 8h
      },

      markAsked: () => set({ askedAt: Date.now() }),
    }),
    { name: 'a20-mood' }
  )
)
