import { expect, test } from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'

const user = {
  user_id: 134,
  email: 'minh.marketing@example.com',
  display_name: 'Minh',
  role: 'learner',
  cefr_level: 'B1',
  industry: 'Marketing',
  learning_goals: ['Email công việc', 'Họp với khách hàng', 'Thuyết trình'],
  preferred_study_time: 'morning',
}

const reviewCards = [
  {
    card_kind: 'error',
    flashcard_id: 901,
    error_type: 'word_choice',
    front: 'Chọn đúng từ: The campaign ___ our sales last week.',
    back: 'affected',
    explanation_vi: '"Affect" là động từ: tác động đến. "Effect" thường là danh từ: kết quả/tác động.',
    cloze_text: 'The new campaign affected our sales last week.',
    interval_days: 1,
  },
  {
    card_kind: 'vocab',
    word_id: 902,
    word: 'measurable',
    pos: 'adjective',
    definition_vi: 'có thể đo lường được',
    example: 'The campaign had a measurable effect on sales.',
    interval_days: 3,
  },
]

test('record one-minute Vietnamese product demo', async ({ page }, testInfo) => {
  await installApiMocks(page)

  await page.addInitScript(() => {
    const today = new Date().toISOString().slice(0, 10)
    localStorage.setItem(
      'a20-mood',
      JSON.stringify({
        state: {
          mood: 'ok',
          derivedConfig: { tone: 'supportive', session_length: 'standard' },
          checkedAt: Date.now(),
          askedAt: Date.now(),
        },
        version: 0,
      }),
    )
    localStorage.setItem(`a20.brief.seen.${today}.134`, '1')
  })

  await page.goto('/app')
  await installVisualEffects(page)
  await expect(page.getByRole('heading', { name: 'Luna' })).toBeVisible()
  await page.waitForTimeout(4_000)

  const input = page.getByPlaceholder('Nhắn tin với gia sư...')
  await input.fill("The new campaign effect our sales last week, but I don't know how to explain it in the meeting.")
  await page.waitForTimeout(1_000)
  await page.getByRole('button', { name: 'Gửi' }).click()
  await expect(page.getByText('affected our sales last week')).toBeVisible({ timeout: 10_000 })

  await highlightWord(page, {
    containingText: 'The new campaign effect our sales last week',
    word: 'effect',
    label: 'Từ dùng sai trong ngữ cảnh này',
  })
  await page.waitForTimeout(2_000)
  await clearVisualEffects(page)

  await zoomText(page, 'Bạn đang rất gần đúng.', 'Luna gợi ý từng bước thay vì chỉ đưa đáp án')
  await highlightWord(page, {
    containingText: 'Effect" thường là danh từ',
    word: 'Effect',
    label: 'So sánh effect / affect',
  })
  await page.waitForTimeout(4_000)
  await clearVisualEffects(page)

  await page.getByRole('button', { name: 'Flashcard' }).first().click()
  await expect(page.getByText('Flashcard sau phiên chat')).toBeVisible()
  await zoomText(page, 'Flashcard sau phiên chat', 'Lỗi trong chat trở thành flashcard ôn tập')
  await page.waitForTimeout(5_000)
  await clearVisualEffects(page)

  await page.getByRole('button', { name: 'Ôn tập' }).first().click()
  await expect(page.getByText('The campaign ___ our sales last week.')).toBeVisible()
  await highlightWord(page, {
    containingText: 'The campaign ___ our sales last week.',
    word: '___',
    label: 'Khoảng trống được ôn lại đúng lúc',
  })
  await page.waitForTimeout(5_000)
  await clearVisualEffects(page)

  await page.goto('/review')
  await expect(page.getByText('Chọn đúng từ')).toBeVisible()
  await page.waitForTimeout(4_000)
  await page.getByRole('button', { name: 'Hiện đáp án' }).click()
  await expect(page.getByText('"Affect" là động từ')).toBeVisible()
  await zoomText(page, '"Affect" là động từ', 'Giải thích cá nhân hóa bằng tiếng Việt')
  await page.waitForTimeout(6_000)
  await clearVisualEffects(page)

  await page.goto('/dashboard')
  await installVisualEffects(page)
  await expect(page.getByText('Báo cáo tiến độ')).toBeVisible()
  await expect(page.getByText('Error DNA')).toBeVisible({ timeout: 10_000 })
  await zoomText(page, 'Error DNA', 'Dashboard biến lỗi lặp lại thành tín hiệu tiến bộ')
  await page.waitForTimeout(12_000)
  await clearVisualEffects(page)

  const video = page.video()
  await page.close()

  if (video) {
    const videoPath = await video.path()
    const targetDir = path.resolve(process.cwd(), '..', '..', 'output', 'demo-video')
    await fs.mkdir(targetDir, { recursive: true })
    await fs.copyFile(videoPath, path.join(targetDir, 'english-tutor-ai-demo.webm'))
    testInfo.attachments.push({
      name: 'demo-video',
      path: path.join(targetDir, 'english-tutor-ai-demo.webm'),
      contentType: 'video/webm',
    })
  }
})

async function installApiMocks(page) {
  await page.route('**/api/v1/auth/me', (route) => route.fulfill(json(user)))
  await page.route('**/api/v1/mood/today', (route) => route.fulfill(json({ mood: 'ok', derived_config: {} })))
  await page.route('**/api/v1/mood', (route) => route.fulfill(json({ mood: 'ok', derived_config: {} })))
  await page.route('**/api/v1/brief/today', (route) => route.fulfill(json({ date: today(), questions: [] })))
  await page.route('**/api/v1/session/restore?**', (route) =>
    route.fulfill(json({
      session: { messages: [] },
      initial_message:
        'Xin chào Minh, mình là Luna. Hôm nay mình sẽ giúp bạn sửa câu tiếng Anh cho cuộc họp Marketing và biến lỗi sai thành bài ôn.',
    })),
  )
  await page.route('**/api/v1/vocabulary/new?**', (route) =>
    route.fulfill(json([
      { word_id: 1, word: 'campaign', definition_vi: 'chiến dịch', pos: 'noun', interval_days: 2 },
      { word_id: 2, word: 'measurable', definition_vi: 'có thể đo lường', pos: 'adjective', interval_days: 3 },
    ])),
  )
  await page.route('**/api/v1/review/due?**', (route) => route.fulfill(json(reviewCards)))
  await page.route('**/api/v1/review/submit', (route) => route.fulfill(json({ ok: true })))
  await page.route('**/api/v1/learning/current?**', (route) => route.fulfill(json(learningPayload('LESSON_READER'))))
  await page.route('**/api/v1/learning/start', (route) => route.fulfill(json(learningPayload('LESSON_READER'))))
  await page.route('**/api/v1/learning/*/questions**', (route) => route.fulfill(json(learningPayload('PRACTICE_RUNNER'))))
  await page.route('**/api/v1/learning/*/flashcards**', (route) => route.fulfill(json(learningPayload('FLASHCARD_RUNNER'))))
  await page.route('**/api/v1/chat', (route) =>
    route.fulfill(json({
      response:
        'Bạn đang rất gần đúng.\n\nHint 1: Trong câu này, từ cần dùng là một động từ vì chiến dịch đã tác động đến doanh số.\n\nHint 2: "Effect" thường là danh từ, còn động từ là "affect".\n\nCâu tự nhiên hơn:\nThe new campaign affected our sales last week.\n\nNếu muốn nói trong cuộc họp:\nThe new campaign had a measurable effect on sales last week.',
      intent: 'ERROR_CORRECTION',
      hint_count: 2,
      ui_directive: {
        action: 'OPEN',
        screen: 'FLASHCARD_RUNNER',
        lesson_id: 'marketing-affect-effect',
      },
      ...learningPayload('FLASHCARD_RUNNER'),
    })),
  )
  await page.route('**/api/v1/analytics/*/summary', (route) =>
    route.fulfill(json({
      profile: user,
      vocabulary: { total_reviews: 42 },
      accuracy_trend: Array.from({ length: 30 }, (_, index) => ({
        date: `05/${String(index + 1).padStart(2, '0')}`,
        accuracy: 58 + Math.round(index * 1.1),
      })),
      recent_errors: [
        {
          id: 1,
          error_type: 'word_choice',
          error_pattern: 'Affect vs effect',
          corrected_text: 'The new campaign affected our sales last week.',
        },
        {
          id: 2,
          error_type: 'preposition',
          error_pattern: 'in/on for meetings',
          corrected_text: 'I will present it in the meeting.',
        },
      ],
      common_error_types: [
        { error: 'word_choice', label: 'Dùng từ', count: 7 },
        { error: 'grammar', label: 'Ngữ pháp', count: 5 },
        { error: 'preposition', label: 'Giới từ', count: 4 },
      ],
    })),
  )
  await page.route('**/api/v1/analytics/*/vocabulary', (route) =>
    route.fulfill(json({ total_learned: 128, mastered: 76 })),
  )
  await page.route('**/api/v1/dna/*', (route) =>
    route.fulfill(json({
      week_start: '2026-05-11',
      dimensions: { grammar: 52, vocab: 68, preposition: 44, writing: 61, collocations: 58, pronunciation: 32 },
      average: { grammar: 45, vocab: 49, preposition: 43, writing: 46, collocations: 41, pronunciation: 38 },
    })),
  )
}

async function installVisualEffects(page) {
  await page.addStyleTag({
    content: `
      .demo-spotlight-target {
        position: relative !important;
        z-index: 2147483001 !important;
        transform: scale(1.22);
        transform-origin: center center;
        transition: transform 420ms ease, box-shadow 420ms ease, outline-color 420ms ease;
        outline: 4px solid rgba(220, 38, 38, 0.95) !important;
        box-shadow: 0 22px 70px rgba(20, 16, 12, 0.28) !important;
      }
      .demo-focus-backdrop {
        position: fixed;
        inset: 0;
        z-index: 2147482998;
        background: rgba(15, 23, 42, 0.16);
        pointer-events: none;
      }
      .demo-callout {
        position: fixed;
        z-index: 2147483002;
        max-width: 360px;
        border-radius: 12px;
        background: rgba(185, 28, 28, 0.96);
        color: white;
        padding: 10px 14px;
        font: 600 15px/1.35 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        box-shadow: 0 16px 50px rgba(120, 20, 20, 0.25);
        pointer-events: none;
      }
      .demo-red-box {
        position: fixed;
        z-index: 2147483003;
        border: 4px solid #dc2626;
        border-radius: 8px;
        box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.08), 0 10px 30px rgba(220, 38, 38, 0.24);
        pointer-events: none;
      }
    `,
  })
  await page.evaluate(() => {
    window.demoFindElementContainingText = (text) => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
      while (walker.nextNode()) {
        const node = walker.currentNode
        if (node.textContent?.includes(text)) {
          return node.parentElement
        }
      }
      return null
    }

    window.demoFindTextRect = (containingText, word) => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
      while (walker.nextNode()) {
        const node = walker.currentNode
        const value = node.textContent || ''
        if (!value.includes(containingText) && !containingText.includes(value.trim())) continue

        const start = value.indexOf(word)
        if (start < 0) continue

        const range = document.createRange()
        range.setStart(node, start)
        range.setEnd(node, start + word.length)
        const rect = range.getBoundingClientRect()
        range.detach()
        if (rect.width > 0 && rect.height > 0) {
          return {
            left: rect.left,
            top: rect.top,
            right: rect.right,
            bottom: rect.bottom,
            width: rect.width,
            height: rect.height,
          }
        }
      }
      return null
    }
  })
}

async function clearVisualEffects(page) {
  await page.evaluate(() => {
    document.querySelectorAll('.demo-spotlight-target').forEach((node) => {
      node.classList.remove('demo-spotlight-target')
    })
    document.querySelectorAll('.demo-focus-backdrop, .demo-callout, .demo-red-box').forEach((node) => node.remove())
  })
}

async function zoomText(page, text, label) {
  await page.evaluate(({ text, label }) => {
    const element = window.demoFindElementContainingText?.(text)
    const target = element?.closest('div[class*="rounded"]') || element
    if (!target) return

    document.querySelectorAll('.demo-focus-backdrop').forEach((node) => node.remove())
    const backdrop = document.createElement('div')
    backdrop.className = 'demo-focus-backdrop'
    document.body.appendChild(backdrop)

    target.classList.add('demo-spotlight-target')
    const rect = target.getBoundingClientRect()
    const callout = document.createElement('div')
    callout.className = 'demo-callout'
    callout.textContent = label
    callout.style.left = `${Math.min(window.innerWidth - 380, Math.max(24, rect.left))}px`
    callout.style.top = `${Math.max(20, rect.top - 58)}px`
    document.body.appendChild(callout)
  }, { text, label })
}

async function highlightWord(page, { containingText, word, label }) {
  await page.evaluate(({ containingText, word, label }) => {
    const rect = window.demoFindTextRect?.(containingText, word)
    if (!rect) return

    const box = document.createElement('div')
    box.className = 'demo-red-box'
    box.style.left = `${Math.max(0, rect.left - 6)}px`
    box.style.top = `${Math.max(0, rect.top - 4)}px`
    box.style.width = `${rect.width + 12}px`
    box.style.height = `${rect.height + 8}px`
    document.body.appendChild(box)

    if (label) {
      const callout = document.createElement('div')
      callout.className = 'demo-callout'
      callout.textContent = label
      callout.style.left = `${Math.min(window.innerWidth - 380, Math.max(24, rect.left - 8))}px`
      callout.style.top = `${Math.min(window.innerHeight - 80, rect.bottom + 14)}px`
      document.body.appendChild(callout)
    }
  }, { containingText, word, label })
}


function learningPayload(screen) {
  return {
    lesson_id: 'marketing-affect-effect',
    ui_directive: { action: 'OPEN', screen, lesson_id: 'marketing-affect-effect' },
    learning_state: { active_lesson_id: 'marketing-affect-effect', current_step: 'FLASHCARD' },
    lesson: {
      lesson_id: 'marketing-affect-effect',
      title: 'Affect vs effect trong báo cáo Marketing',
      cefr_level: 'B1',
      objective: 'Dùng đúng affect/effect khi mô tả kết quả chiến dịch.',
      explanation_vi:
        'Khi muốn nói một chiến dịch tác động đến doanh số, dùng "affect" như động từ. Khi nói về tác động/kết quả, dùng "effect" như danh từ.',
      markdown:
        '## Khi nào dùng affect/effect?\n\n- **Affect** là động từ: tác động đến.\n- **Effect** thường là danh từ: kết quả hoặc tác động.\n\nVí dụ: **The new campaign affected our sales last week.**',
      examples: [
        'The new campaign affected our sales last week.',
        'The campaign had a measurable effect on sales.',
      ],
    },
    questions: [
      {
        question_id: 'q1',
        type: 'multiple_choice_abcd',
        prompt: 'The campaign ___ our sales last week.',
        choices: [
          { key: 'A', text: 'effect' },
          { key: 'B', text: 'affected' },
          { key: 'C', text: 'effective' },
          { key: 'D', text: 'effectively' },
        ],
        correct_answer: 'B',
        explanation_vi: 'Cần động từ quá khứ, nên dùng "affected".',
      },
    ],
    cards: [
      {
        card_id: 'fc1',
        front: 'Flashcard sau phiên chat: The campaign ___ our sales.',
        back: {
          definition_vi: 'affected. "Affect" là động từ; "effect" thường là danh từ.',
          example: 'The campaign had a measurable effect on sales.',
        },
      },
    ],
  }
}

function json(body) {
  return {
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  }
}

function today() {
  return new Date().toISOString().slice(0, 10)
}
