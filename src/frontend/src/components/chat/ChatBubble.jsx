export default function ChatBubble({ message }) {
  const isUser = message.role === 'user'
  const roleLabel = isUser ? 'Bạn' : 'Tutor'

  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
      role="article"
      aria-label={`Tin nhắn từ ${roleLabel}`}
    >
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? 'bg-blue-500 text-white rounded-br-md'
            : 'bg-gray-100 text-gray-900 rounded-bl-md dark:bg-slate-800 dark:text-slate-100'
        }`}
      >
        <div aria-label={`${roleLabel}: ${message.content}`}>
          {message.content}
        </div>
        {message.hint_count != null && message.hint_count > 0 && (
          <div
            className="text-xs mt-1 opacity-70"
            role="status"
            aria-label={`Đã sử dụng ${message.hint_count} trong 2 gợi ý`}
          >
            💡 Hint {message.hint_count}/2
          </div>
        )}
      </div>
    </div>
  )
}
