import { useState } from 'react'

export default function InputBox({ onSend, onGiveUp, disabled }) {
  const [text, setText] = useState('')

  const submit = () => {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText('')
  }

  return (
    <div className="border-t bg-white p-3 flex items-end gap-2 dark:border-slate-800 dark:bg-slate-900">
      <button
        type="button"
        onClick={onGiveUp}
        disabled={disabled}
        aria-label="Bỏ cuộc - Hiện đáp án"
        className="px-3 py-2 rounded-xl border border-gray-300 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-red-500 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
      >
        Give up
      </button>
      <div className="flex-1">
        <label htmlFor="chat-input" className="sr-only">
          Nhập câu trả lời hoặc câu hỏi
        </label>
        <textarea
          id="chat-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
          rows={1}
          placeholder="Nhập câu trả lời hoặc câu hỏi…"
          aria-label="Nhập câu trả lời hoặc câu hỏi (Shift+Enter để xuống dòng)"
          className="w-full resize-none border rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 max-h-32 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
        />
      </div>
      <button
        type="button"
        disabled={disabled || !text.trim()}
        onClick={submit}
        aria-label="Gửi tin nhắn"
        className="px-4 py-2 rounded-xl bg-blue-500 text-white disabled:bg-gray-300 hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-blue-600 disabled:cursor-not-allowed dark:disabled:bg-slate-700"
      >
        Gửi
      </button>
    </div>
  )
}
