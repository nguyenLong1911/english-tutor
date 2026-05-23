import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { getErrorMessage, tutorAPI } from '../services/api.js'
import { useAuthStore } from '../stores/authStore.js'
import { useChatStore } from '../stores/chatStore.js'
import { useMoodStore } from '../stores/moodStore.js'
import RichTextContent from '../components/common/RichTextContent.jsx'
import MoodCheckInModal from '../components/common/MoodCheckInModal.jsx'
import MorningBriefOverlay from '../components/common/MorningBriefOverlay.jsx'
import LearningWindow from '../components/learning/LearningWindow.jsx'

const navItems = [
  { label: 'Chat', icon: ChatIcon, screen: null },
  { label: 'Bài giảng', icon: BookIcon, screen: 'LESSON_READER' },
  { label: 'Ôn tập', icon: ChartIcon, screen: 'PRACTICE_RUNNER' },
  { label: 'Flashcard', icon: CardsIcon, screen: 'FLASHCARD_RUNNER' },
]

const PANEL_MIN_WIDTH = 320
const PANEL_OPEN_RATIO = 2 / 3
const PANEL_MAX_SCREEN_RATIO = 0.75
const CHAT_MIN_WIDTH = 360
const SIDEBAR_WIDTH = 240
const MOBILE_BREAKPOINT = 768
const DESKTOP_PANEL_BREAKPOINT = 1280

export default function ChatPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const messages = useChatStore((s) => s.messages)
  const appendMessage = useChatStore((s) => s.appendMessage)
  const setMessages = useChatStore((s) => s.setMessages)
  const bindUser = useChatStore((s) => s.bindUser)
  const resetMessages = useChatStore((s) => s.reset)
  const scrollRef = useRef(null)
  const resizeStateRef = useRef(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const [panelWidth, setPanelWidth] = useState(420)
  const [isResizing, setIsResizing] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [viewportWidth, setViewportWidth] = useState(() => (typeof window === 'undefined' ? 1280 : window.innerWidth))
  const [notice, setNotice] = useState('')
  const [learningScreen, setLearningScreen] = useState('CHAT')
  const [learningData, setLearningData] = useState(null)
  const [learningLoading, setLearningLoading] = useState(false)
  const [learningError, setLearningError] = useState('')
  const learningRequestRef = useRef({ key: null, promise: null })

  const userId = user?.user_id
  const isMobileViewport = viewportWidth < MOBILE_BREAKPOINT
  const useOverlayPanel = viewportWidth < DESKTOP_PANEL_BREAKPOINT
  const leftWidth = sidebarOpen ? SIDEBAR_WIDTH : 0
  const clampedPanelWidth = panelOpen ? clampPanelWidth(panelWidth, leftWidth) : 0

  const openLearningPanel = useCallback(() => {
    setPanelWidth(getDefaultPanelWidth(leftWidth))
    setPanelOpen(true)
  }, [leftWidth])

  // Target architecture: mood check-in + morning brief overlay (§9.1, §9.4)
  const moodHydrate = useMoodStore((s) => s.hydrate)
  const moodShouldAsk = useMoodStore((s) => s.shouldAsk)
  const [moodOpen, setMoodOpen] = useState(false)
  const [briefOpen, setBriefOpen] = useState(false)

  useEffect(() => {
    if (!userId) {
      resetMessages()
      setPanelOpen(false)
      setLearningScreen('CHAT')
      setLearningData(null)
      setLearningLoading(false)
      setLearningError('')
      setNotice('')
      return
    }
    bindUser(userId)
    setPanelOpen(false)
    setLearningScreen('CHAT')
    setLearningData(null)
    setLearningLoading(false)
    setLearningError('')
    setNotice('')
  }, [bindUser, resetMessages, userId])

  useEffect(() => {
    if (!userId) return
    moodHydrate()
    if (moodShouldAsk()) setMoodOpen(true)
    const briefSeenKey = `a20.brief.seen.${new Date().toISOString().slice(0, 10)}.${userId}`
    if (typeof window !== 'undefined' && !window.localStorage.getItem(briefSeenKey)) {
      setBriefOpen(true)
      window.localStorage.setItem(briefSeenKey, '1')
    }
  }, [userId, moodHydrate, moodShouldAsk])

  const applyLearningPayload = useCallback((payload, shouldOpen = true) => {
    if (!payload) return
    setLearningData(payload)
    setLearningScreen(resolveLearningScreen(payload))
    setLearningError('')
    if (shouldOpen && payload?.ui_directive?.action === 'OPEN') {
      openLearningPanel()
    }
  }, [openLearningPanel])

  const hydrateLearningDirective = useCallback(async (payload, shouldOpen = true) => {
    if (!payload?.ui_directive || !userId) return
    const directive = payload.ui_directive
    if (directive.action !== 'OPEN') {
      applyLearningPayload(payload, false)
      return
    }

    const screen = resolveLearningScreen(payload)
    const lessonId = getLearningLessonId(payload)
    setLearningLoading(true)
    setLearningError('')
    if (shouldOpen) openLearningPanel()

    try {
      let hydrated = payload
      if (screen === 'LESSON_READER' && !payload.lesson) {
        hydrated = await tutorAPI.getCurrentLearning(userId)
      } else if (screen === 'PRACTICE_RUNNER' && !payload.questions?.length && lessonId) {
        hydrated = await tutorAPI.getLessonQuestions(lessonId, userId)
      } else if (screen === 'FLASHCARD_RUNNER' && !payload.cards?.length && lessonId) {
        hydrated = await tutorAPI.getLessonFlashcards(lessonId, userId)
      }
      applyLearningPayload(hydrated, shouldOpen)
    } catch (error) {
      setLearningError(getErrorMessage(error, 'chat.learning'))
      applyLearningPayload(payload, shouldOpen)
    } finally {
      setLearningLoading(false)
    }
  }, [applyLearningPayload, openLearningPanel, userId])

  useEffect(() => {
    let cancelled = false
    const restoreLearning = async () => {
      if (!userId) return
      try {
        const payload = await tutorAPI.getCurrentLearning(userId)
        if (!cancelled) {
          applyLearningPayload(payload, false)
        }
      } catch {
        if (!cancelled) setLearningError('Không khôi phục được cửa sổ học hiện tại.')
      }
    }
    restoreLearning()
    return () => {
      cancelled = true
    }
  }, [applyLearningPayload, userId])

  const {
    data: vocabulary = [],
  } = useQuery({
    queryKey: ['vocabulary', userId],
    queryFn: () => tutorAPI.getNewVocabulary(userId, 6),
    enabled: Boolean(userId),
    retry: false,
  })

  const {
    data: dueReviews = [],
  } = useQuery({
    queryKey: ['review-due', userId],
    queryFn: () => tutorAPI.getReviewDue(userId, 10),
    enabled: Boolean(userId),
    retry: false,
  })

  useEffect(() => {
    if (!userId || vocabulary.length === 0) return
    queryClient.invalidateQueries({ queryKey: ['review-due', userId] })
  }, [queryClient, userId, vocabulary.length])

  useEffect(() => {
    let cancelled = false
    const restore = async () => {
      if (!userId || messages.length > 0) return
      let result = null
      try {
        result = await tutorAPI.restoreSession(userId)
        if (cancelled) return
        if (result?.session?.messages?.length) {
          setMessages(result.session.messages, userId)
          setNotice('Tiếp tục từ phiên học gần nhất.')
          return
        }
      } catch {
        // New users do not have a session yet.
      }
      const initialMessage =
        result?.initial_message ||
        'Xin chào, mình là Luna. Bạn có thể nhắn "Mở bài giảng đầu tiên", "Mở ôn tập cho bài này", hoặc "Mở flashcard cho bài này".'
      if (cancelled) return
      appendMessage({
        role: 'assistant',
        content: initialMessage,
        timestamp: new Date().toISOString(),
      }, userId)
    }
    restore()
    return () => {
      cancelled = true
    }
  }, [appendMessage, messages.length, setMessages, userId])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  useEffect(() => {
    const handleResize = () => setViewportWidth(window.innerWidth)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  useEffect(() => {
    if (!notice) return undefined
    const timer = window.setTimeout(() => setNotice(''), 2800)
    return () => window.clearTimeout(timer)
  }, [notice])

  useEffect(() => {
    if (!panelOpen) return undefined
    const handleResize = () => {
      setPanelWidth((width) => clampPanelWidth(width, leftWidth))
    }
    window.addEventListener('resize', handleResize)
    handleResize()
    return () => window.removeEventListener('resize', handleResize)
  }, [leftWidth, panelOpen])

  useEffect(() => {
    if (!isResizing) return undefined
    const previousCursor = document.body.style.cursor
    const previousUserSelect = document.body.style.userSelect
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    return () => {
      document.body.style.cursor = previousCursor
      document.body.style.userSelect = previousUserSelect
    }
  }, [isResizing])

  const chatMutation = useMutation({
    mutationFn: (payload) => tutorAPI.chat(userId, payload),
    onSuccess: (response) => {
      appendMessage({
        role: 'assistant',
        content: response.response,
        intent: response.intent,
        hint_count: response.hint_count,
        timestamp: new Date().toISOString(),
      })
      hydrateLearningDirective(response)
    },
    onError: (error) => {
      const message = getErrorMessage(error, 'chat.send')
      setNotice(message)
      appendMessage({
        role: 'assistant',
        content: message,
        timestamp: new Date().toISOString(),
      })
    },
  })

  const sendMessage = (message) => {
    if (!userId) {
      setNotice('Bạn cần đăng nhập trước khi chat.')
      return
    }
    appendMessage({ role: 'user', content: message, timestamp: new Date().toISOString() })
    const moodState = useMoodStore.getState().mood
    chatMutation.mutate({ message, ...(moodState ? { mood_state: moodState } : {}) })
  }

  const runLearningRequest = useCallback(async (requestKey, request) => {
    if (!userId) {
      setNotice('Bạn cần đăng nhập trước khi học.')
      return null
    }
    if (learningRequestRef.current.promise) {
      if (learningRequestRef.current.key === requestKey) {
        return learningRequestRef.current.promise
      }
      return null
    }
    setLearningLoading(true)
    setLearningError('')
    openLearningPanel()
    const pendingRequest = (async () => {
      try {
        const payload = await request()
        applyLearningPayload(payload, true)
        return payload
      } catch (error) {
        const message = getErrorMessage(error, 'chat.learning')
        setLearningError(message)
        setNotice(message)
        return null
      } finally {
        setLearningLoading(false)
        learningRequestRef.current = { key: null, promise: null }
      }
    })()
    learningRequestRef.current = { key: requestKey, promise: pendingRequest }
    return pendingRequest
  }, [applyLearningPayload, openLearningPanel, userId])

  const handleLearningAction = useCallback(async (intent) => {
    const currentLessonId = getLearningLessonId(learningData)
    if (intent === 'START_LEARNING') {
      await runLearningRequest('start-learning', () => tutorAPI.startLearning(userId))
      return
    }
    if (intent === 'READ_LESSON') {
      if (currentLessonId) {
        await runLearningRequest(`lesson-read:${currentLessonId}`, () => tutorAPI.startLearning(userId, currentLessonId))
      } else {
        await runLearningRequest('lesson-read:start', () => tutorAPI.startLearning(userId))
      }
      return
    }
    if (intent === 'LESSON_PRACTICE' || intent === 'SUBMIT_PRACTICE') {
      if (currentLessonId) {
        await runLearningRequest(`lesson-practice:${currentLessonId}`, () => tutorAPI.getLessonQuestions(currentLessonId, userId))
      } else {
        const started = await runLearningRequest('lesson-practice:start', () => tutorAPI.startLearning(userId))
        const startedLessonId = getLearningLessonId(started)
        if (startedLessonId) {
          await runLearningRequest(`lesson-practice:${startedLessonId}`, () => tutorAPI.getLessonQuestions(startedLessonId, userId))
        }
      }
      return
    }
    if (intent === 'LESSON_FLASHCARD') {
      if (currentLessonId) {
        await runLearningRequest(`lesson-flashcard:${currentLessonId}`, () => tutorAPI.getLessonFlashcards(currentLessonId, userId))
      } else {
        const started = await runLearningRequest('lesson-flashcard:start', () => tutorAPI.startLearning(userId))
        const startedLessonId = getLearningLessonId(started)
        if (startedLessonId) {
          await runLearningRequest(`lesson-flashcard:${startedLessonId}`, () => tutorAPI.getLessonFlashcards(startedLessonId, userId))
        }
      }
      return
    }
    if (intent === 'LESSON_COMPLETE' && currentLessonId) {
      await runLearningRequest(`lesson-complete:${currentLessonId}`, () => tutorAPI.completeLesson(currentLessonId, userId))
      return
    }
    if (intent === 'NEXT_LESSON') {
      const nextLessonId = learningData?.next_lesson_id || learningData?.ui_directive?.next_lesson_id
      await runLearningRequest(`next-lesson:${nextLessonId || 'default'}`, () => tutorAPI.startLearning(userId, nextLessonId || null))
    }
  }, [learningData, runLearningRequest, userId])

  const handleLearningScreenSelect = useCallback((screen) => {
    openLearningPanel()
    setLearningScreen(screen)
    if (hasLoadedScreenData(learningData, screen)) {
      setLearningError('')
      return
    }
    if (screen === 'LESSON_READER') {
      handleLearningAction('READ_LESSON')
    } else if (screen === 'PRACTICE_RUNNER') {
      handleLearningAction('LESSON_PRACTICE')
    } else if (screen === 'FLASHCARD_RUNNER') {
      handleLearningAction('LESSON_FLASHCARD')
    }
  }, [handleLearningAction, openLearningPanel])

  const handlePracticeSubmit = useCallback(async (answers) => {
    const lessonId = getLearningLessonId(learningData)
    const practiceSetId = learningData?.practice_set_id || learningData?.ui_directive?.practice_set_id
    if (!lessonId || !practiceSetId) {
      setNotice('Thiếu practice_set_id để nộp bài.')
      return
    }
    await runLearningRequest(
      `practice-submit:${lessonId}:${practiceSetId}`,
      () => tutorAPI.submitLessonQuestions(lessonId, userId, practiceSetId, answers)
    )
  }, [learningData, runLearningRequest, userId])

  const handleNav = (item) => {
    if (!item.screen) {
      setPanelOpen(false)
      if (isMobileViewport) setSidebarOpen(false)
      return
    }
    handleLearningScreenSelect(item.screen)
    if (isMobileViewport) setSidebarOpen(false)
  }

  const handlePanelResizeStart = (event) => {
    if (!panelOpen) return
    event.preventDefault()
    const handle = event.currentTarget
    const pointerId = event.pointerId
    handle.setPointerCapture?.(pointerId)
    const startX = event.clientX
    const startWidth = clampedPanelWidth
    resizeStateRef.current = { startX, startWidth }
    setIsResizing(true)

    const handlePointerMove = (moveEvent) => {
      moveEvent.preventDefault()
      const resizeState = resizeStateRef.current
      if (!resizeState) return
      const nextWidth = resizeState.startWidth + resizeState.startX - moveEvent.clientX
      setPanelWidth(clampPanelWidth(nextWidth, leftWidth))
    }

    const stopResizing = () => {
      handle.releasePointerCapture?.(pointerId)
      resizeStateRef.current = null
      setIsResizing(false)
      document.removeEventListener('pointermove', handlePointerMove)
      document.removeEventListener('pointerup', stopResizing)
      document.removeEventListener('pointercancel', stopResizing)
      window.removeEventListener('blur', stopResizing)
    }

    document.addEventListener('pointermove', handlePointerMove)
    document.addEventListener('pointerup', stopResizing)
    document.addEventListener('pointercancel', stopResizing)
    window.addEventListener('blur', stopResizing)
  }

  const handlePanelResizeKeyDown = (event) => {
    if (!panelOpen) return
    const step = event.shiftKey ? 40 : 16
    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      setPanelWidth((width) => clampPanelWidth(width + step, leftWidth))
    } else if (event.key === 'ArrowRight') {
      event.preventDefault()
      setPanelWidth((width) => clampPanelWidth(width - step, leftWidth))
    } else if (event.key === 'Home') {
      event.preventDefault()
      setPanelWidth(PANEL_MIN_WIDTH)
    } else if (event.key === 'End') {
      event.preventDefault()
      setPanelWidth(clampPanelWidth(window.innerWidth * PANEL_MAX_SCREEN_RATIO, leftWidth))
    }
  }

  const handleLogout = async () => {
    resetMessages()
    await logout()
    navigate('/', { replace: true })
  }

  const memoryCount = vocabulary.length + dueReviews.length

  return (
    <>
    <MoodCheckInModal open={moodOpen} onClose={() => setMoodOpen(false)} />
    {briefOpen && <MorningBriefOverlay onClose={() => setBriefOpen(false)} />}
    <div className="h-screen overflow-hidden bg-[var(--cream-0)] text-[var(--ink)]">
      <div className={`grid h-full md:grid-cols-[var(--left-width)_minmax(0,1fr)] ${panelOpen ? 'xl:grid-cols-[var(--left-width)_minmax(0,1fr)_var(--panel-width)]' : 'xl:grid-cols-[var(--left-width)_minmax(0,1fr)_0px]'} ${isResizing ? '' : 'transition-[grid-template-columns] duration-200'}`} style={{ '--left-width': `${leftWidth}px`, '--panel-width': `${clampedPanelWidth}px` }}>
        <aside
          className={`${
          isMobileViewport
            ? `fixed inset-y-0 left-0 z-40 max-w-[82vw] shadow-xl transition-transform duration-200 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`
            : `hidden min-h-0 md:col-start-1 md:row-start-1 md:flex-col ${sidebarOpen ? 'md:flex' : 'md:hidden'}`
        } border-r border-[var(--line)] bg-[var(--cream-2)] p-4 xl:p-5`}
          style={isMobileViewport ? { width: SIDEBAR_WIDTH } : undefined}
        >
          <div className={sidebarOpen ? 'flex items-start gap-3' : 'flex flex-col items-center gap-3'}>
            {sidebarOpen ? (
              <Link to="/" className="logo min-w-0 flex-1 pr-2 text-[1.8rem] xl:text-[2rem]">
                Lingo·AI
                <span className="mt-2 block font-sans text-sm font-normal tracking-normal text-[var(--muted)]">Scholar Tier</span>
              </Link>
            ) : (
              <Link to="/" className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[var(--ochre)] font-semibold text-white">L</Link>
            )}
            <button className="grid h-10 w-10 shrink-0 place-items-center self-start rounded-full bg-[var(--ochre-soft)] text-[var(--ochre)]" onClick={() => setSidebarOpen((value) => !value)} type="button" aria-label={sidebarOpen ? 'Thu gọn menu' : 'Mở menu'}>
              <MenuIcon />
            </button>
          </div>

          <nav className={`${sidebarOpen ? 'mt-7 xl:mt-10' : 'mt-6'} space-y-2 xl:space-y-3`}>
            {navItems.map((item) => {
              const Icon = item.icon
              const active = item.screen ? panelOpen && isScreenActive(learningScreen, item.screen) : !panelOpen
              return (
                <button className={`flex w-full items-center rounded-xl py-2.5 text-left transition ${sidebarOpen ? 'gap-4 px-4' : 'justify-center px-0'} ${active ? 'bg-[var(--ochre-bright)] text-[var(--ink)]' : 'text-[var(--muted)] hover:bg-[var(--cream-3)]'}`} key={item.label} onClick={() => handleNav(item)} type="button" aria-label={item.label}>
                  <Icon />
                  {sidebarOpen ? <span className="text-lg">{item.label}</span> : null}
                </button>
              )
            })}
          </nav>

          <div className="mt-auto space-y-5 border-t border-[var(--line)] pt-5">
            {sidebarOpen ? (
              <div className="rounded-xl border border-[#cfd9be] bg-[var(--green-soft)] px-4 py-3 text-sm text-[var(--green)]">
                <p className="font-semibold">Memory Synced</p>
                <p className="mt-1 text-[var(--muted)]">Recalling {memoryCount} vocab items.</p>
              </div>
            ) : null}
            <div className="flex items-center gap-3">
              <div className="grid h-9 w-9 place-items-center rounded-full bg-[var(--ochre)] font-semibold text-white">
                {(user?.display_name || user?.email || 'U').slice(0, 1).toUpperCase()}
              </div>
              {sidebarOpen ? (
                <div className="min-w-0">
                  <p className="truncate font-semibold">{user?.display_name || 'Learner'}</p>
                  <button className="text-sm text-[var(--muted)] underline underline-offset-2" onClick={handleLogout} type="button">
                    Đăng xuất
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </aside>
        {isMobileViewport && sidebarOpen ? (
          <button
            aria-label="Đóng menu"
            className="fixed inset-0 z-30 bg-[rgba(28,20,12,0.24)]"
            onClick={() => setSidebarOpen(false)}
            type="button"
          />
        ) : null}

        <section className="flex min-h-0 flex-col border-r border-[var(--line)] bg-[var(--cream-0)] md:col-start-2 md:row-start-1">
          <header className="flex min-h-[66px] items-center justify-between border-b border-[var(--line)] bg-[rgba(255,250,247,0.92)] px-5">
            <div className="flex items-center gap-3">
              {!sidebarOpen ? (
                <button className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[var(--ochre-soft)] text-[var(--ochre)]" onClick={() => setSidebarOpen(true)} type="button" aria-label="Mở menu">
                  <MenuIcon />
                </button>
              ) : null}
              <div className="grid h-10 w-10 place-items-center rounded-full bg-[var(--ochre-soft)] text-[var(--ochre)]">
                <BotIcon />
              </div>
              <div>
                <h1 className="text-xl font-semibold leading-none">Luna</h1>
              </div>
            </div>
            <div className="hidden gap-2 sm:flex">
              {[
                ['LESSON_READER', 'Bài giảng'],
                ['PRACTICE_RUNNER', 'Ôn tập'],
                ['FLASHCARD_RUNNER', 'Flashcard'],
              ].map(([value, label]) => (
                <button className={`rounded-full border px-4 py-2 text-sm ${isScreenActive(learningScreen, value) && panelOpen ? 'border-[var(--ochre)] bg-[var(--ochre-soft)] text-[var(--ochre)]' : 'border-[var(--line)] bg-white text-[var(--muted)]'}`} key={value} onClick={() => handleLearningScreenSelect(value)} type="button">
                  {label}
                </button>
              ))}
            </div>
          </header>

          <nav className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-4 border-t border-[var(--line)] bg-[var(--cream-2)] px-2 py-2 md:hidden">
            {navItems.map((item) => {
              const Icon = item.icon
              const active = item.screen ? panelOpen && isScreenActive(learningScreen, item.screen) : !panelOpen
              return (
                <button className={`flex flex-col items-center gap-1 rounded-xl px-2 py-2 text-xs ${active ? 'bg-[var(--ochre-bright)] text-[var(--ink)]' : 'text-[var(--muted)]'}`} key={item.label} onClick={() => handleNav(item)} type="button">
                  <Icon />
                  <span>{item.label}</span>
                </button>
              )
            })}
          </nav>

          {notice ? <div className="border-b border-[var(--line)] bg-[var(--ochre-soft)] px-5 py-2 text-sm text-[var(--muted)]">{notice}</div> : null}

          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 pb-24 md:pb-5" ref={scrollRef}>
            <div className="mx-auto flex max-w-[780px] flex-col gap-5">
              {messages.map((message, index) => (
                <MessageBubble key={`${message.role}-${message.timestamp || index}`} message={message} />
              ))}
              {chatMutation.isPending ? <TypingIndicator /> : null}
            </div>
          </div>

          <ChatInput disabled={chatMutation.isPending} onSend={sendMessage} />
        </section>

        <aside className={`relative hidden min-h-0 overflow-hidden bg-white xl:col-start-3 xl:row-start-1 xl:block ${panelOpen ? 'border-l border-[var(--line)]' : 'border-l-0'} ${isResizing ? '' : 'transition-[width] duration-200'}`}>
          {panelOpen ? (
            <button
              aria-label="Resize learning panel"
              aria-orientation="vertical"
              aria-valuemax={Math.round(window.innerWidth * PANEL_MAX_SCREEN_RATIO)}
              aria-valuemin={PANEL_MIN_WIDTH}
              aria-valuenow={clampedPanelWidth}
              className="group absolute left-0 top-0 z-20 hidden h-full w-5 cursor-col-resize touch-none items-center justify-center bg-transparent outline-none transition hover:bg-[var(--ochre-soft)] focus-visible:bg-[var(--ochre-soft)] xl:flex"
              onKeyDown={handlePanelResizeKeyDown}
              onPointerDown={handlePanelResizeStart}
              role="separator"
              title="Resize panel"
              type="button"
            >
              <span className="h-full w-px bg-[var(--line-strong)] opacity-70 transition group-hover:opacity-100" />
            </button>
          ) : null}
          <LearningWindow
            data={learningData}
            dueCount={dueReviews.length}
            error={learningError}
            learnedCount={vocabulary.length + dueReviews.length}
            loading={learningLoading}
            onAction={handleLearningAction}
            onClose={() => setPanelOpen(false)}
            onSelectScreen={handleLearningScreenSelect}
            onSubmitPractice={handlePracticeSubmit}
            open={panelOpen}
            screen={learningScreen}
          />
        </aside>
        {useOverlayPanel && panelOpen ? (
          <>
            <button
              aria-label="Đóng cửa sổ học"
              className="fixed inset-0 z-40 bg-[rgba(28,20,12,0.28)]"
              onClick={() => setPanelOpen(false)}
              type="button"
            />
            <aside className="fixed inset-x-0 bottom-0 top-0 z-50 bg-white md:inset-6 md:rounded-[28px] md:shadow-2xl">
              <LearningWindow
                data={learningData}
                dueCount={dueReviews.length}
                error={learningError}
                learnedCount={vocabulary.length + dueReviews.length}
                loading={learningLoading}
                onAction={handleLearningAction}
                onClose={() => setPanelOpen(false)}
                onSelectScreen={handleLearningScreenSelect}
                onSubmitPractice={handlePracticeSubmit}
                open={panelOpen}
                screen={learningScreen}
              />
            </aside>
          </>
        ) : null}
      </div>
    </div>
    </>
  )
}

function hasLoadedScreenData(data, screen) {
  if (!data) return false
  if (screen === 'LESSON_READER') return Boolean(data.lesson)
  if (screen === 'PRACTICE_RUNNER') return Array.isArray(data.questions) && data.questions.length > 0
  if (screen === 'FLASHCARD_RUNNER') return Array.isArray(data.cards) && data.cards.length > 0
  return false
}

function clampPanelWidth(width, leftWidth) {
  if (typeof window === 'undefined') {
    return Math.max(PANEL_MIN_WIDTH, width)
  }
  const availableMax = window.innerWidth - leftWidth - CHAT_MIN_WIDTH
  const maxWidth = Math.max(PANEL_MIN_WIDTH, Math.min(window.innerWidth * PANEL_MAX_SCREEN_RATIO, availableMax))
  return Math.min(maxWidth, Math.max(PANEL_MIN_WIDTH, width))
}

function getDefaultPanelWidth(leftWidth) {
  if (typeof window === 'undefined') {
    return PANEL_MIN_WIDTH
  }
  return clampPanelWidth(window.innerWidth * PANEL_OPEN_RATIO, leftWidth)
}

function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  const richTextVariant = isUser
    ? {
        article: 'space-y-3 text-[1.02rem] leading-relaxed text-[var(--ink)]',
        paragraph: 'text-[var(--ink)] whitespace-pre-wrap',
        list: 'space-y-2 pl-5 text-[var(--ink)]',
        code: 'rounded bg-white/70 px-1 py-0.5 font-mono-ui text-[var(--ink)]',
        strong: 'font-semibold text-[var(--ink)]',
        emphasis: 'italic text-[var(--ink)]',
        details: 'rounded-xl border border-white/60 bg-white/50 p-4',
        summary: 'cursor-pointer font-semibold text-[var(--ink)]',
        detailsBody: 'mt-4 space-y-3',
      }
    : {
        article: 'space-y-3 text-[1.02rem] leading-relaxed text-[var(--ink)]',
        paragraph: 'text-[var(--ink)] whitespace-pre-wrap',
        list: 'space-y-2 pl-5 text-[var(--ink)]',
      }
  return (
    <div className={`flex items-start gap-4 ${isUser ? 'justify-end' : ''}`}>
      {!isUser ? <AvatarIcon /> : null}
      <div className={`${isUser ? 'max-w-[72%] rounded-[18px_18px_4px_18px] bg-[var(--cream-3)]' : 'max-w-[76%] rounded-[18px_18px_18px_4px] border border-[var(--line)] bg-white'} px-4 py-3 text-[1.02rem] leading-relaxed shadow-sm`}>
        <RichTextContent content={message.content} variant={richTextVariant} />
        {!isUser && message.hint_count > 0 ? (
          <p className="mt-3 text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ochre)]">
            Hint {message.hint_count}/2
          </p>
        ) : null}
      </div>
      {isUser ? <div className="h-9 w-9 rounded-full bg-[var(--ink)]" /> : null}
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex items-start gap-4">
      <AvatarIcon />
      <div className="flex items-center gap-1 rounded-xl border border-[var(--line)] bg-white px-5 py-4">
        {[0, 1, 2].map((item) => <span className="h-2 w-2 rounded-full bg-[var(--muted)] [animation:dots_1s_ease-in-out_infinite]" style={{ animationDelay: `${item * 150}ms` }} key={item} />)}
      </div>
    </div>
  )
}

function ChatInput({ disabled, onSend }) {
  const [value, setValue] = useState('')

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  return (
    <div className="border-t border-[var(--line)] bg-[var(--cream-0)] px-4 py-3 pb-20 md:pb-3">
      <div className="mx-auto max-w-[780px]">
        <div className="flex items-end gap-3 rounded-2xl border border-[var(--line)] bg-white p-3">
          <textarea className="max-h-32 min-h-[42px] flex-1 resize-none bg-transparent px-2 py-2 outline-none" disabled={disabled} onChange={(event) => setValue(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submit() } }} placeholder="Nhắn tin với gia sư..." rows={1} value={value} />
          <button className="grid h-10 w-10 place-items-center rounded-xl bg-[var(--ochre-bright)] text-[var(--ink)] disabled:opacity-40" disabled={disabled || !value.trim()} onClick={submit} type="button" aria-label="Gửi">
            <SendIcon />
          </button>
        </div>
        <p className="mt-2 text-xs text-[var(--muted-soft)]">Enter để gửi · Shift+Enter xuống dòng</p>
      </div>
    </div>
  )
}

function resolveLearningScreen(payload) {
  const directiveScreen = payload?.ui_directive?.screen
  if (directiveScreen) return directiveScreen
  const step = payload?.learning_state?.current_step || payload?.state?.current_step
  return {
    LESSON_READING: 'LESSON_READER',
    PRACTICE: 'PRACTICE_RUNNER',
    FLASHCARD: 'FLASHCARD_RUNNER',
    LESSON_COMPLETE: 'LESSON_COMPLETE',
    NONE: 'CHAT',
  }[step] || 'CHAT'
}

function getLearningLessonId(payload) {
  return (
    payload?.lesson_id ||
    payload?.completed_lesson_id ||
    payload?.ui_directive?.lesson_id ||
    payload?.learning_state?.active_lesson_id ||
    payload?.state?.active_lesson_id ||
    payload?.lesson?.lesson_id ||
    null
  )
}

function isScreenActive(currentScreen, targetScreen) {
  if (currentScreen === targetScreen) return true
  return currentScreen === 'PRACTICE_RESULT' && targetScreen === 'PRACTICE_RUNNER'
}

function AvatarIcon() {
  return <div className="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full border border-[var(--line-strong)] bg-[var(--cream-2)] text-[var(--ochre)]"><BotIcon /></div>
}

function IconBase({ children }) {
  return <svg aria-hidden="true" className="h-5 w-5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.9" viewBox="0 0 24 24">{children}</svg>
}

function ChatIcon() { return <IconBase><path d="M4 5h16v11H8l-4 4V5Z" /></IconBase> }
function BookIcon() { return <IconBase><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15Z" /></IconBase> }
function CardsIcon() { return <IconBase><path d="m7 8 10-3 3 10-10 3-3-10Z" /><path d="M4 8v11h11" /></IconBase> }
function ChartIcon() { return <IconBase><path d="M4 20h16" /><path d="M7 16V8" /><path d="M12 16V4" /><path d="M17 16v-6" /></IconBase> }
function MenuIcon() { return <IconBase><path d="M4 7h16" /><path d="M4 12h10" /><path d="M4 17h16" /></IconBase> }
function BotIcon() { return <IconBase><path d="M12 8V5" /><rect height="10" rx="2" width="14" x="5" y="8" /><path d="M9 12h.01" /><path d="M15 12h.01" /></IconBase> }
function CloseIcon() { return <IconBase><path d="M18 6 6 18" /><path d="m6 6 12 12" /></IconBase> }
function SendIcon() { return <IconBase><path d="m22 2-7 20-4-9-9-4 20-7Z" /><path d="M22 2 11 13" /></IconBase> }
