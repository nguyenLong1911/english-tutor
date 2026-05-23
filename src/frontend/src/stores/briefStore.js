import { create } from 'zustand'
import { briefAPI, getErrorMessage } from '../services/api.js'

const getTodayKey = () => new Date().toISOString().slice(0, 10)

// Morning Brief (§9.4): 3 retrieval Qs at the start of the day.
export const useBriefStore = create((set, get) => ({
  date: null,
  questions: [],
  loading: false,
  submitting: false,
  submitted: false,
  error: null,

  load: async () => {
    if (get().loading) return
    set({ loading: true, error: null })
    try {
      const data = await briefAPI.today()
      const questions = (data.questions || []).map((q) => ({
        ...q,
        userAnswer: '',
        revealed: false,
        quality: null,
        answer_correct: null,
        brief_skip_until: null,
        error_flashcard_id: null,
        next_review: null,
        mastered: false,
      }))
      set({
        date: data.date || getTodayKey(),
        questions,
        loading: false,
        submitting: false,
        submitted: false,
      })
    } catch (err) {
      set({ loading: false, error: getErrorMessage(err, 'brief.load') })
    }
  },

  setAnswer: (idx, value) =>
    set((s) => {
      const next = s.questions.slice()
      if (next[idx]) next[idx] = { ...next[idx], userAnswer: value }
      return { questions: next }
    }),

  reveal: (idx) =>
    set((s) => {
      const next = s.questions.slice()
      if (next[idx]) next[idx] = { ...next[idx], revealed: true }
      return { questions: next }
    }),

  rate: (idx, quality) =>
    set((s) => {
      const next = s.questions.slice()
      if (next[idx]) next[idx] = { ...next[idx], quality, revealed: true }
      return { questions: next }
    }),

  submit: async () => {
    if (get().submitting) return
    const answers = get().questions
      .filter((q) => Number.isInteger(q.quality))
      .map((q) => ({ word_id: q.word_id, quality: q.quality, user_answer: q.userAnswer }))
    if (answers.length === 0 || answers.length !== get().questions.length) return
    try {
      set({ submitting: true, error: null })
      const data = await briefAPI.submit(answers)
      const updates = new Map((data.updated || []).map((item) => [item.word_id, item]))
      set((s) => ({
        submitting: false,
        submitted: true,
        questions: s.questions.map((q) => {
          const update = updates.get(q.word_id)
          return update ? { ...q, ...update, revealed: true } : q
        }),
      }))
    } catch (err) {
      set({ submitting: false, error: getErrorMessage(err, 'brief.submit') })
    }
  },

  reset: () => set({ date: null, questions: [], loading: false, submitting: false, submitted: false, error: null }),
}))
