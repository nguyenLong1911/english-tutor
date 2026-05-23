import axios from 'axios'

const baseURL = import.meta.env.VITE_API_URL || ''

const DEFAULT_ERROR_MESSAGE = 'Đã có lỗi xảy ra. Vui lòng thử lại sau.'

const CONTEXT_MESSAGES = {
  'admin.load': 'Không tải được dashboard admin. Vui lòng thử lại sau.',
  'analytics.load': 'Không tải được báo cáo tiến độ. Vui lòng thử lại sau.',
  'auth.google': 'Đăng nhập Google chưa hoàn tất. Vui lòng thử lại.',
  'auth.login': 'Email hoặc mật khẩu chưa đúng.',
  'auth.signup': 'Không tạo được tài khoản. Vui lòng kiểm tra thông tin và thử lại.',
  'brief.load': 'Không tải được Morning Brief hôm nay.',
  'brief.submit': 'Không lưu được câu trả lời Morning Brief.',
  'chat.learning': 'Không tải được nội dung học. Vui lòng thử lại.',
  'chat.send': 'Tin nhắn chưa gửi được. Vui lòng thử lại.',
  'context.analyze': 'Không phân tích được nội dung này. Vui lòng rút gọn hoặc thử lại sau.',
  'dashboard.dna': 'Không tải được Error DNA.',
  'gdpr.delete': 'Không xóa được dữ liệu lúc này. Vui lòng thử lại sau.',
  'onboarding.save': 'Không lưu được onboarding. Vui lòng thử lại.',
  'password.forgot': 'Không gửi được email đặt lại mật khẩu. Vui lòng thử lại.',
  'password.reset': 'Không đặt lại được mật khẩu. Liên kết có thể đã hết hạn.',
  'profile.save': 'Không lưu được hồ sơ. Vui lòng thử lại.',
  'review.load': 'Không tải được thẻ ôn tập. Vui lòng thử lại.',
  'review.submit': 'Không lưu được kết quả ôn tập. Vui lòng thử lại.',
}

const DETAIL_MESSAGES = [
  [/email already registered/i, 'Email này đã được đăng ký. Vui lòng đăng nhập hoặc dùng email khác.'],
  [/invalid email or password/i, 'Email hoặc mật khẩu chưa đúng.'],
  [/invalid or expired token/i, 'Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.'],
  [/password confirmation required/i, 'Vui lòng nhập mật khẩu để xác nhận xóa dữ liệu.'],
  [/daily rate limit exceeded/i, 'Bạn đã dùng hết lượt chat hôm nay. Vui lòng quay lại sau.'],
  [/unauthorized|forbidden|invalid admin token|missing x-admin-token/i, 'Bạn không có quyền thực hiện thao tác này.'],
  [/user not found|user\/word pair not found|user\/flashcard pair not found/i, 'Không tìm thấy dữ liệu phù hợp cho tài khoản hiện tại.'],
  [/practice set not found/i, 'Phiên luyện tập này đã hết hạn. Vui lòng mở lại bài ôn tập.'],
  [/text required/i, 'Vui lòng nhập nội dung cần phân tích.'],
  [/text exceeds 4kb/i, 'Nội dung quá dài. Vui lòng rút gọn trước khi phân tích.'],
]

export class AppError extends Error {
  constructor(message, { status, code, detail, traceId, isNetworkError = false } = {}) {
    super(message)
    this.name = 'AppError'
    this.status = status
    this.code = code
    this.detail = detail
    this.traceId = traceId
    this.isNetworkError = isNetworkError
  }
}

function normalizeDetail(detail) {
  if (!detail) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(normalizeDetail).filter(Boolean).join('; ')
  if (typeof detail === 'object') {
    return detail.msg || detail.message || detail.error || ''
  }
  return String(detail)
}

function messageFromDetail(detail) {
  const normalized = normalizeDetail(detail)
  const match = DETAIL_MESSAGES.find(([pattern]) => pattern.test(normalized))
  return match?.[1] || ''
}

function messageFromStatus(status, fallback) {
  if (status === 400 || status === 422) return 'Thông tin gửi lên chưa hợp lệ. Vui lòng kiểm tra lại.'
  if (status === 401) return 'Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.'
  if (status === 403) return 'Bạn không có quyền thực hiện thao tác này.'
  if (status === 404) return 'Không tìm thấy dữ liệu cần dùng.'
  if (status === 409) return 'Dữ liệu đã tồn tại hoặc bị trùng.'
  if (status === 429) return 'Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút.'
  if (status >= 500) return fallback || DEFAULT_ERROR_MESSAGE
  return fallback || DEFAULT_ERROR_MESSAGE
}

export function getErrorMessage(error, context, fallback) {
  if (!error) return fallback || CONTEXT_MESSAGES[context] || DEFAULT_ERROR_MESSAGE
  if (error.isNetworkError) return 'Không kết nối được máy chủ. Vui lòng kiểm tra mạng và thử lại.'
  const contextMessage = CONTEXT_MESSAGES[context] || fallback
  return messageFromDetail(error.detail) || contextMessage || DEFAULT_ERROR_MESSAGE
}

function toAppError(err) {
  const response = err?.response
  const status = response?.status
  const detail = response?.data?.detail || response?.data?.error || response?.data?.message
  const traceId = response?.headers?.['x-trace-id'] || response?.data?.trace_id
  const isNetworkError = !response
  const message = isNetworkError
    ? 'Không kết nối được máy chủ. Vui lòng kiểm tra mạng và thử lại.'
    : messageFromDetail(detail) || messageFromStatus(status)
  return new AppError(message, {
    status,
    code: response?.data?.code,
    detail,
    traceId,
    isNetworkError,
  })
}

export const http = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 65000,
  withCredentials: true,
})

http.interceptors.response.use(
  (r) => r,
  (err) => {
    return Promise.reject(toAppError(err))
  }
)

export const authAPI = {
  register: (data) => http.post('/api/v1/auth/register', data).then((r) => r.data),
  login: (email, password) =>
    http.post('/api/v1/auth/login', { email, password }).then((r) => r.data),
  logout: () => http.post('/api/v1/auth/logout').then((r) => r.data),
  me: () => http.get('/api/v1/auth/me').then((r) => r.data),

  // Google OAuth: /start is a 302 to Google's consent screen, so we full-page
  // navigate to it via the same origin (Vite proxies /api → backend in dev).
  googleStartUrl: () => `${baseURL}/api/v1/auth/google/start`,
  googleCallback: (code, state) =>
    http.post('/api/v1/auth/google/callback', { code, state }).then((r) => r.data),
}

export const tutorAPI = {
  onboarding: (data) => http.post('/api/v1/onboarding', data).then((r) => r.data),

  createDemoUser: () => http.post('/api/v1/onboarding/demo').then((r) => r.data),

  getUser: (userId) => http.get(`/api/v1/user/${userId}`).then((r) => r.data),

  getNewVocabulary: (userId, limit = 3) =>
    http.get('/api/v1/vocabulary/new', { params: { user_id: userId, limit } }).then((r) => r.data),

  getReviewDue: (userId, limit = 20) =>
    http.get('/api/v1/review/due', { params: { user_id: userId, limit } }).then((r) => r.data),

  submitReview: (userId, card, quality) => {
    const body = {
      user_id: userId,
      card_kind: card?.card_kind || 'vocab',
      quality,
    }
    if (body.card_kind === 'error') {
      body.flashcard_id = card.flashcard_id
    } else {
      body.word_id = typeof card === 'object' ? card.word_id : card
    }
    return http
      .post('/api/v1/review/submit', body)
      .then((r) => r.data)
  },

  submitVocabularyReview: (userId, wordId, quality) =>
    http
      .post('/api/v1/review/submit', { user_id: userId, word_id: wordId, quality })
      .then((r) => r.data),

  chat: (userId, payload) => {
    const body = typeof payload === 'string' ? { message: payload } : payload
    return http.post('/api/v1/chat', { user_id: userId, ...body }).then((r) => r.data)
  },

  getCurrentLearning: (userId) =>
    http.get('/api/v1/learning/current', { params: { user_id: userId } }).then((r) => r.data),

  startLearning: (userId, lessonId = null) =>
    http.post('/api/v1/learning/start', { user_id: userId, lesson_id: lessonId }).then((r) => r.data),

  getLessonQuestions: (lessonId, userId) =>
    http.post(`/api/v1/learning/${lessonId}/questions`, { user_id: userId }).then((r) => r.data),

  submitLessonQuestions: (lessonId, userId, practiceSetId, answers) =>
    http
      .post(`/api/v1/learning/${lessonId}/questions/submit`, {
        user_id: userId,
        practice_set_id: practiceSetId,
        answers,
      })
      .then((r) => r.data),

  getLessonFlashcards: (lessonId, userId) =>
    http.get(`/api/v1/learning/${lessonId}/flashcards`, { params: { user_id: userId } }).then((r) => r.data),

  completeLesson: (lessonId, userId) =>
    http.post(`/api/v1/learning/${lessonId}/complete`, { user_id: userId }).then((r) => r.data),

  restoreSession: (userId) =>
    http.get('/api/v1/session/restore', { params: { user_id: userId } }).then((r) => r.data),

  deleteSession: (userId) =>
    http.delete(`/api/v1/session/${userId}`).then((r) => r.data),

  // Sprint 3: Analytics
  getAnalyticsSummary: (userId) =>
    http.get(`/api/v1/analytics/${userId}/summary`).then((r) => r.data),

  getAnalyticsVocabulary: (userId) =>
    http.get(`/api/v1/analytics/${userId}/vocabulary`).then((r) => r.data),

  // Sprint 3: User
  deleteUser: (userId) =>
    http.delete(`/api/v1/user/${userId}`).then((r) => r.data),

  updateUserPreferences: (userId, preferences) =>
    http.post(`/api/v1/user/${userId}/preferences`, preferences).then((r) => r.data),

}

// ── Target architecture endpoints ─────────────────────────────────────
export const moodAPI = {
  set: (mood) => http.post('/api/v1/mood', { mood }).then((r) => r.data),
  today: () => http.get('/api/v1/mood/today').then((r) => r.data),
}

export const contextAPI = {
  analyze: (text, language = 'en') =>
    http.post('/api/v1/context/analyze', { text, language }).then((r) => r.data),
}

export const briefAPI = {
  today: () => http.get('/api/v1/brief/today').then((r) => r.data),
  submit: (answers) => http.post('/api/v1/brief/submit', { answers }).then((r) => r.data),
}

export const dnaAPI = {
  forUser: (userId) => http.get(`/api/v1/dna/${userId}`).then((r) => r.data),
}

export const adminAPI = {
  dashboard: () => http.get('/api/v1/admin/dashboard').then((r) => r.data),
  users: (params = {}) => http.get('/api/v1/admin/dashboard/users', { params }).then((r) => r.data),
  exportCsv: async () => {
    const response = await http.get('/api/v1/admin/dashboard.csv', { responseType: 'blob' })
    return response.data
  },
}

export const gdprAPI = {
  delete: (password) =>
    http.post('/api/v1/gdpr/delete', password ? { password } : {}).then((r) => r.data),
  audit: () => http.get('/api/v1/gdpr/audit').then((r) => r.data),
}

export const authResetAPI = {
  forgot: (email) => http.post('/api/v1/auth/forgot', { email }).then((r) => r.data),
  reset: (token, newPassword) =>
    http.post('/api/v1/auth/reset', { token, new_password: newPassword }).then((r) => r.data),
}
