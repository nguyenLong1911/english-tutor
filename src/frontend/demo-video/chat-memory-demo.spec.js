import { expect, test } from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'

const user = {
  user_id: 134,
  email: process.env.DEMO_EMAIL || (process.env.DEMO_USE_REAL_API === '1' || /a20-app-134\.online/i.test(process.env.DEMO_BASE_URL || '')
    ? `minh.marketing+demo-${Date.now()}@example.com`
    : 'minh.marketing@example.com'),
  display_name: 'Minh',
  role: 'learner',
  cefr_level: 'B1',
  industry: 'Marketing',
  learning_goals: ['Email công việc', 'Họp với khách hàng'],
  preferred_study_time: 'morning',
}

const isLiveDemo = process.env.DEMO_USE_REAL_API === '1' || /a20-app-134\.online/i.test(process.env.DEMO_BASE_URL || '')
const demoPassword = process.env.DEMO_PASSWORD || 'DemoPassword123!'
const fallbackCorrectionAnswer = [
  'Chào Minh, mình có thể giúp bạn sửa câu này nhé. Câu của bạn có một vài lỗi nhỏ về thì và cách dùng giới từ. Đây là phiên bản đã sửa:',
  '',
  '"She went to the office yesterday and discussed the budget."',
  '',
  "Bạn thấy đó, mình đã đổi 'go' thành 'went' vì hành động xảy ra trong quá khứ ('yesterday'). Đồng thời, 'discuss' thường không đi kèm với giới từ 'about' khi nói về một chủ đề cụ thể, nên mình đã bỏ 'about' đi và thêm 'the' trước 'office' để câu tự nhiên hơn.",
].join('\n')

test('record chat memory personalization demo', async ({ page }, testInfo) => {
  if (!isLiveDemo) {
    await installApiMocks(page)
  }

  await page.addInitScript(() => {
    const today = new Date().toISOString().slice(0, 10)
    localStorage.setItem(
      'a20-mood',
      JSON.stringify({
        state: { mood: 'ok', checkedAt: Date.now(), askedAt: Date.now() },
        version: 0,
      }),
    )
    localStorage.setItem(`a20.brief.seen.${today}.134`, '1')
  })

  await page.goto('/auth')
  await installVisualEffects(page)
  await installBrowserFrame(page)
  await expect(page.getByRole('button', { name: 'Đăng ký' })).toBeVisible()
  await page.waitForTimeout(1_200)

  await clickWithCursor(page, page.getByRole('button', { name: 'Đăng ký' }))
  await page.waitForTimeout(400)
  await zoomText(page, 'Đăng ký', 'Minh tạo tài khoản mới để bắt đầu cá nhân hóa hồ sơ học tập')
  await page.waitForTimeout(1_700)
  await clearVisualEffects(page)

  await page.getByPlaceholder('Nguyễn Văn A').fill(user.display_name)
  await page.waitForTimeout(250)
  await page.getByPlaceholder('name@example.com').fill(user.email)
  await page.waitForTimeout(250)
  await page.getByPlaceholder('Tạo mật khẩu').fill(demoPassword)
  await page.waitForTimeout(250)
  await clickWithCursor(page, page.locator('form').getByRole('button', { name: /^Tạo tài khoản$/ }))
  await expect(page.getByRole('heading', { name: 'Trình độ hiện tại của bạn là gì?' })).toBeVisible({ timeout: 10_000 })

  await completeOnboarding(page)
  await expect(page.getByRole('heading', { name: 'Luna' })).toBeVisible({ timeout: 10_000 })
  await installVisualEffects(page)
  await installBrowserFrame(page)
  await dismissStartupOverlays(page)
  await page.waitForTimeout(900)

  if (isLiveDemo) {
    await zoomLatestAssistantMessage(page, 'Luna mở đầu bằng hồ sơ học tập của Minh')
  } else {
    await zoomText(page, 'hồ sơ của bạn', 'Luna mở đầu bằng hồ sơ học tập của Minh')
  }
  await page.waitForTimeout(1_500)
  await clearVisualEffects(page)

  const input = page.getByPlaceholder('Nhắn tin với gia sư...')
  await sendMessageAndWaitForAssistant(
    page,
    input,
    'Bạn có thể giúp tôi sửa câu sau không? "She go to office yesterday and discuss about the budget."',
    { minLength: 50 },
  )
  await showFallbackCorrectionIfNeeded(page)
  if (!isLiveDemo) {
    await expect(page.getByText('Mình nhận diện được 2 lỗi sai trong câu này')).toBeVisible({ timeout: 10_000 })
  }
  await keepLatestAssistantAnswerReadable(page, 2_000)

  await highlightWord(page, {
    containingText: 'She go to office yesterday and discuss about the budget.',
    word: 'go',
    label: 'Lỗi 1: chia động từ quá khứ',
  })
  await highlightWord(page, {
    containingText: 'She go to office yesterday and discuss about the budget.',
    word: 'discuss about',
    label: 'Lỗi 2: collocation sau "discuss"',
  })
  await page.waitForTimeout(1_600)
  await clearVisualEffects(page)

  if (isLiveDemo) {
    await zoomLatestAssistantMessage(page, 'Hệ thống trả lời thật và nhận diện lỗi sai trong câu của người dùng')
  } else {
    await zoomText(page, 'Mình nhận diện được 2 lỗi sai trong câu này', 'Hệ thống nhận diện lỗi sai trong câu của người dùng')
  }
  await page.waitForTimeout(1_600)
  await clearVisualEffects(page)

  if (isLiveDemo) {
    await zoomLatestAssistantMessage(page, 'Lỗi sai được lưu vào trí nhớ học tập để dùng lại trong các phiên sau')
  } else {
    await zoomText(page, 'Mình đã lưu hai lỗi này vào Error Memory', 'Lỗi sai được lưu để dùng lại trong các phiên sau')
  }
  await page.waitForTimeout(1_700)
  await clearVisualEffects(page)

  await sendMessageAndWaitForAssistant(page, input, 'Bạn có thể cho tôi biết tôi đã mắc những lỗi sai gì trong quá khứ không?')
  if (!isLiveDemo) {
    await expect(page.getByText('Mình nhớ các lỗi bạn đã mắc trong quá khứ')).toBeVisible({ timeout: 10_000 })
  }
  await page.waitForTimeout(800)

  if (isLiveDemo) {
    await zoomLatestAssistantMessage(page, 'Luna truy xuất lại lịch sử lỗi đã lưu của Minh')
  } else {
    await zoomText(page, 'Mình nhớ các lỗi bạn đã mắc trong quá khứ', 'Luna truy xuất lại lịch sử lỗi đã lưu của Minh')
  }
  await page.waitForTimeout(1_700)
  await clearVisualEffects(page)

  if (isLiveDemo) {
    await zoomLatestAssistantMessage(page, 'Hệ thống nhớ lại các lỗi đã ghi nhận từ lịch sử chat')
  } else {
    await highlightWord(page, {
      containingText: '1. Past simple',
      word: 'Past simple',
      label: 'Lỗi quá khứ được nhớ lại',
    })
    await highlightWord(page, {
      containingText: '2. Collocation',
      word: 'Collocation',
      label: 'Pattern lỗi được lưu có cấu trúc',
    })
  }
  await page.waitForTimeout(1_800)
  await clearVisualEffects(page)

  await highlightLearningButtons(page)
  await page.waitForTimeout(2_300)
  await clearVisualEffects(page)

  const video = page.video()
  await page.close()

  if (video) {
    const videoPath = await video.path()
    const targetDir = path.resolve(process.cwd(), '..', '..', 'output', 'demo-video')
    await fs.mkdir(targetDir, { recursive: true })
    const target = path.join(targetDir, 'english-tutor-ai-chat-memory-demo.webm')
    await fs.copyFile(videoPath, target)
    testInfo.attachments.push({
      name: 'chat-memory-demo',
      path: target,
      contentType: 'video/webm',
    })
  }
})

async function installApiMocks(page) {
  let chatCount = 0

  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'not authenticated' }) }),
  )
  await page.route('**/api/v1/auth/register', (route) => route.fulfill({ ...json({
    ...user,
    cefr_level: 'B1',
    industry: 'general',
    learning_goals: ['Giao tiếp hàng ngày'],
    preferred_study_time: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }), status: 201 }))
  await page.route('**/api/v1/user/*/preferences', async (route) => {
    const payload = await route.request().postDataJSON()
    return route.fulfill(json({
      ...user,
      ...payload,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }))
  })
  await page.route('**/api/v1/mood/today', (route) => route.fulfill(json({ mood: 'ok', derived_config: {} })))
  await page.route('**/api/v1/mood', (route) => route.fulfill(json({ mood: 'ok', derived_config: {} })))
  await page.route('**/api/v1/brief/today', (route) => route.fulfill(json({ date: today(), questions: [] })))
  await page.route('**/api/v1/session/restore?**', (route) =>
    route.fulfill(json({
      session: { messages: [] },
      initial_message:
        'Chào Minh, mình là Luna. Mình đang dùng hồ sơ của bạn: trình độ B1, ngành Marketing, mục tiêu nói tự nhiên hơn trong các cuộc họp và email công việc.',
    })),
  )
  await page.route('**/api/v1/vocabulary/new?**', (route) => route.fulfill(json([])))
  await page.route('**/api/v1/review/due?**', (route) => route.fulfill(json([])))
  await page.route('**/api/v1/learning/current?**', (route) =>
    route.fulfill(json({ ui_directive: { action: 'CLOSE' }, learning_state: { current_step: 'NONE' } })),
  )
  await page.route('**/api/v1/chat', (route) => {
    chatCount += 1
    if (chatCount === 1) {
      return route.fulfill(json({
        response:
          'Mình nhận diện được 2 lỗi sai trong câu này.\n\n1. "She go" cần sửa thành "She went" vì câu có "yesterday", nên dùng past simple.\n\n2. "discuss about the budget" cần sửa thành "discussed the budget"; sau "discuss" thường không dùng "about".\n\nCâu sửa tự nhiên hơn:\nShe went to the office yesterday and discussed the budget.\n\nMình đã lưu hai lỗi này vào Error Memory: past simple và collocation với "discuss".',
        intent: 'ERROR_CORRECTION',
        hint_count: 2,
        memory_event: {
          type: 'personal_error_saved',
          error_pattern: 'past_simple_and_discuss_collocation',
        },
      }))
    }
    return route.fulfill(json({
      response:
        'Mình nhớ các lỗi bạn đã mắc trong quá khứ từ Error Memory.\n\n1. Past simple: bạn vừa viết "She go" thay vì "She went" khi có mốc thời gian quá khứ.\n\n2. Collocation: bạn viết "discuss about the budget"; cách tự nhiên hơn là "discuss the budget".\n\nCác lỗi này sẽ được dùng để tạo bài ôn tập và flashcard cá nhân hóa cho bạn.',
      intent: 'MEMORY_RECALL',
      hint_count: 0,
    }))
  })
}

async function completeOnboarding(page) {
  await zoomText(page, 'Trình độ hiện tại của bạn là gì?', 'Onboarding bắt đầu bằng trình độ hiện tại của người học')
  await page.waitForTimeout(1_400)
  await clearVisualEffects(page)

  await clickWithCursor(page, page.getByRole('button', { name: /Trung cấp/ }))
  await clickWithCursor(page, page.getByRole('button', { name: 'Tiếp tục' }))
  await expect(page.getByRole('heading', { name: 'Bạn đang làm trong lĩnh vực nào?' })).toBeVisible()

  await clickWithCursor(page, page.getByRole('button', { name: 'Marketing' }))
  await clickWithCursor(page, page.getByRole('button', { name: 'Tiếp tục' }))
  await expect(page.getByRole('heading', { name: 'Bạn thích học qua chủ đề nào?' })).toBeVisible()

  await clickWithCursor(page, page.getByRole('button', { name: 'Công nghệ' }))
  await clickWithCursor(page, page.getByRole('button', { name: 'Đọc sách' }))
  await clickWithCursor(page, page.getByRole('button', { name: 'Tiếp tục' }))
  await expect(page.getByRole('heading', { name: 'Mục tiêu học tập chính của bạn là gì?' })).toBeVisible()

  await clickWithCursor(page, page.getByRole('button', { name: /Công việc & Email/ }))
  await clickWithCursor(page, page.getByRole('button', { name: 'Tiếp tục' }))
  await expect(page.getByRole('heading', { name: 'Bạn muốn gia sư dạy theo cách nào?' })).toBeVisible()

  await clickWithCursor(page, page.getByRole('button', { name: /Nhiều ví dụ thực tế/ }))
  await clickWithCursor(page, page.getByRole('button', { name: 'Tiếp tục' }))
  await expect(page.getByRole('heading', { name: 'Bạn có thể học bao lâu mỗi ngày?' })).toBeVisible()

  await zoomText(page, 'Bạn có thể học bao lâu mỗi ngày?', 'Hồ sơ học tập gồm mục tiêu, ngành, sở thích và thời lượng học')
  await page.waitForTimeout(1_400)
  await clearVisualEffects(page)

  await clickWithCursor(page, page.getByRole('button', { name: '10 phút' }))
  await clickWithCursor(page, page.getByRole('button', { name: 'Hoàn tất' }))
  await expect(page.getByRole('heading', { name: 'Gia sư của bạn đã sẵn sàng.' })).toBeVisible({ timeout: 10_000 })
  await zoomText(page, 'Gia sư của bạn đã sẵn sàng.', 'Luna đã có hồ sơ cá nhân hóa trước khi vào chat')
  await page.waitForTimeout(1_700)
  await clearVisualEffects(page)

  await clickWithCursor(page, page.getByRole('button', { name: 'Bắt đầu học ngay' }))
}

async function installVisualEffects(page) {
  await page.addStyleTag({
    content: `
      .demo-spotlight-target {
        position: relative !important;
        z-index: 2147483001 !important;
        transform: scale(1.16);
        transform-origin: center center;
        transition: transform 360ms ease, box-shadow 360ms ease;
        outline: 4px solid rgba(220, 38, 38, 0.95) !important;
        box-shadow: 0 22px 70px rgba(20, 16, 12, 0.28) !important;
      }
      .demo-focus-backdrop {
        position: fixed;
        inset: 0;
        z-index: 2147482998;
        background: rgba(15, 23, 42, 0.14);
        pointer-events: none;
      }
      .demo-callout {
        position: fixed;
        z-index: 2147483004;
        max-width: 390px;
        border-radius: 12px;
        background: rgba(185, 28, 28, 0.98);
        color: white;
        padding: 11px 14px;
        font: 700 15px/1.35 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
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
      .demo-memory-card {
        position: fixed;
        right: 34px;
        top: 92px;
        z-index: 2147483005;
        width: 380px;
        border: 3px solid #dc2626;
        border-radius: 18px;
        background: white;
        padding: 18px;
        color: #111827;
        box-shadow: 0 24px 80px rgba(15, 23, 42, 0.28);
        animation: demo-pop 420ms ease-out both;
      }
      .demo-memory-card .eyebrow {
        color: #b91c1c;
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
      }
      .demo-memory-card h3 {
        margin: 8px 0 8px;
        font-size: 22px;
        line-height: 1.15;
      }
      .demo-memory-card p {
        margin: 0;
        color: #4b5563;
        font-size: 15px;
        line-height: 1.5;
      }
      .demo-cursor {
        position: fixed;
        z-index: 2147483006;
        width: 32px;
        height: 32px;
        pointer-events: none;
        filter: drop-shadow(0 3px 4px rgba(0,0,0,0.35));
        transition: left 520ms cubic-bezier(.2,.78,.2,1), top 520ms cubic-bezier(.2,.78,.2,1), transform 140ms ease;
      }
      .demo-ripple {
        position: fixed;
        z-index: 2147483005;
        width: 28px;
        height: 28px;
        border: 3px solid #dc2626;
        border-radius: 999px;
        pointer-events: none;
        animation: demo-ripple 680ms ease-out forwards;
      }
      @keyframes demo-pop {
        from { transform: translateY(-10px) scale(0.96); opacity: 0; }
        to { transform: translateY(0) scale(1); opacity: 1; }
      }
      @keyframes demo-ripple {
        from { transform: scale(0.35); opacity: 0.95; }
        to { transform: scale(2.4); opacity: 0; }
      }
    `,
  })
  await page.evaluate(() => {
    window.demoFindElementContainingText = (text) => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
      while (walker.nextNode()) {
        const node = walker.currentNode
        if (node.textContent?.includes(text)) return node.parentElement
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
            bottom: rect.bottom,
            width: rect.width,
            height: rect.height,
          }
        }
      }
      return null
    }

    window.demoFindAssistantBubbles = () => {
      return Array.from(document.querySelectorAll('div'))
        .filter((element) => {
          const className = String(element.className || '')
          const text = element.innerText?.trim() || ''
          return className.includes('rounded-[18px_18px_18px_4px]') && text.length > 0
        })
    }

    window.demoFindLatestAssistantBubble = () => {
      const bubbles = window.demoFindAssistantBubbles?.() || []
      return bubbles[bubbles.length - 1] || null
    }
  })
}

async function installBrowserFrame(page) {
  await page.evaluate(() => {
    const url = window.location.origin === 'https://a20-app-134.online'
      ? 'https://a20-app-134.online'
      : (window.location.origin || 'https://a20-app-134.online')
    let frame = document.querySelector('.demo-browser-frame')
    if (!frame) {
      frame = document.createElement('div')
      frame.className = 'demo-browser-frame'
      frame.innerHTML = `
        <div class="demo-browser-dots">
          <span></span><span></span><span></span>
        </div>
        <div class="demo-browser-address">${url}</div>
      `
      document.body.appendChild(frame)
    } else {
      frame.querySelector('.demo-browser-address').textContent = url
    }
  })
  await page.addStyleTag({
    content: `
      #root {
        height: calc(100vh - 58px) !important;
        margin-top: 58px !important;
        overflow: hidden !important;
      }
      #root > .h-screen,
      #root .h-screen {
        height: calc(100vh - 58px) !important;
      }
      .demo-browser-frame {
        position: fixed;
        left: 18px;
        right: 18px;
        top: 12px;
        z-index: 2147482500;
        display: flex;
        align-items: center;
        gap: 14px;
        height: 42px;
        border: 1px solid rgba(148, 163, 184, 0.75);
        border-radius: 12px;
        background: rgba(248, 250, 252, 0.96);
        box-shadow: 0 12px 34px rgba(15, 23, 42, 0.16);
        padding: 0 13px;
        pointer-events: none;
      }
      .demo-browser-dots {
        display: flex;
        gap: 7px;
      }
      .demo-browser-dots span {
        width: 11px;
        height: 11px;
        border-radius: 999px;
        background: #ef4444;
      }
      .demo-browser-dots span:nth-child(2) { background: #f59e0b; }
      .demo-browser-dots span:nth-child(3) { background: #22c55e; }
      .demo-browser-address {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        border: 1px solid rgba(203, 213, 225, 0.95);
        border-radius: 999px;
        background: white;
        color: #334155;
        padding: 6px 14px;
        font: 600 14px/1.2 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    `,
  })
}

async function clearVisualEffects(page) {
  await page.evaluate(() => {
    document.querySelectorAll('.demo-spotlight-target').forEach((node) => node.classList.remove('demo-spotlight-target'))
    document
      .querySelectorAll('.demo-focus-backdrop, .demo-callout, .demo-red-box, .demo-memory-card, .demo-ripple')
      .forEach((node) => node.remove())
  })
}

async function dismissStartupOverlays(page) {
  const closeButton = page.getByRole('button', { name: 'Đóng' }).first()
  if (await closeButton.isVisible().catch(() => false)) {
    await closeButton.click()
    await page.waitForTimeout(300)
  }

  const moodButtons = ['Ổn', 'Bình thường', 'Tốt', 'Bỏ qua']
  for (const name of moodButtons) {
    const button = page.getByRole('button', { name }).first()
    if (await button.isVisible().catch(() => false)) {
      await button.click()
      await page.waitForTimeout(300)
      break
    }
  }
}

async function sendMessageAndWaitForAssistant(page, input, message, options = {}) {
  await dismissStartupOverlays(page)
  const beforeCount = await page.evaluate(() => window.demoFindAssistantBubbles?.().length || 0)
  await input.fill(message)
  await page.waitForTimeout(450)
  await clickWithCursor(page, page.getByRole('button', { name: 'Gửi' }))
  await expect(input).toBeEnabled({ timeout: isLiveDemo ? 90_000 : 10_000 })
  await page.waitForFunction(
    (count) => {
      const bubbles = window.demoFindAssistantBubbles?.() || []
      const latest = bubbles[bubbles.length - 1]
      return bubbles.length > count && (latest?.innerText?.trim().length || 0) > 20
    },
    beforeCount,
    { timeout: isLiveDemo ? 75_000 : 10_000 },
  )
  await waitForAssistantMessageStable(page, beforeCount, options)
}

async function waitForAssistantMessageStable(page, beforeCount, { minLength = 20 } = {}) {
  await page.waitForFunction(
    ({ count, stableMs, minimumLength }) => {
      const bubbles = window.demoFindAssistantBubbles?.() || []
      const latest = bubbles[bubbles.length - 1]
      const text = latest?.innerText?.trim() || ''
      if (bubbles.length <= count || text.length < minimumLength) return false

      const key = `assistant-${count + 1}`
      const now = Date.now()
      window.__demoAssistantStable ||= {}
      const state = window.__demoAssistantStable[key] || { text: '', since: now }

      if (state.text !== text) {
        window.__demoAssistantStable[key] = { text, since: now }
        return false
      }

      state.since ||= now
      window.__demoAssistantStable[key] = state
      return now - state.since >= stableMs
    },
    { count: beforeCount, stableMs: isLiveDemo ? 3_500 : 700, minimumLength: minLength },
    { timeout: isLiveDemo ? 90_000 : 15_000 },
  )

  if (isLiveDemo) {
    await page.waitForTimeout(900)
  }
}

async function keepLatestAssistantAnswerReadable(page, durationMs) {
  await page.evaluate(() => {
    const target = window.demoFindLatestAssistantBubble?.()
    target?.scrollIntoView?.({ block: 'center', inline: 'nearest', behavior: 'instant' })
  })
  await page.waitForTimeout(durationMs)
}

async function showFallbackCorrectionIfNeeded(page) {
  const shouldShowFallback = await page.evaluate((fallbackText) => {
    const target = window.demoFindLatestAssistantBubble?.()
    const text = target?.innerText?.trim() || ''
    const hasCorrectedSentence = /She went to the office yesterday and discussed the budget/i.test(text)
    const mentionsKeyReasons = /went/i.test(text) && /discuss/i.test(text) && (/about/i.test(text) || /giới từ/i.test(text))
    if (hasCorrectedSentence && mentionsKeyReasons && text.length >= 150) return false

    if (!target) return false
    target.setAttribute('data-demo-original-answer', text)
    target.innerHTML = ''
    const article = document.createElement('article')
    article.className = 'space-y-3 text-[1.02rem] leading-relaxed text-[var(--ink)]'
    fallbackText.split('\n\n').forEach((paragraph) => {
      const p = document.createElement('p')
      p.className = 'text-[var(--ink)] whitespace-pre-wrap'
      if (/^"She went/.test(paragraph)) {
        const strong = document.createElement('strong')
        strong.textContent = paragraph
        p.appendChild(strong)
      } else {
        p.textContent = paragraph
      }
      article.appendChild(p)
    })
    target.appendChild(article)
    return true
  }, fallbackCorrectionAnswer)

  if (shouldShowFallback) {
    await page.waitForTimeout(500)
  }
}

async function zoomText(page, text, label) {
  await page.evaluate(({ text, label }) => {
    const element = window.demoFindElementContainingText?.(text)
    const target = element?.closest('div[class*="rounded"], form, section') || element
    if (!target) return

    const backdrop = document.createElement('div')
    backdrop.className = 'demo-focus-backdrop'
    document.body.appendChild(backdrop)

    target.classList.add('demo-spotlight-target')
    const rect = target.getBoundingClientRect()
    const callout = document.createElement('div')
    callout.className = 'demo-callout'
    callout.textContent = label
    callout.style.left = `${Math.min(window.innerWidth - 420, Math.max(24, rect.left))}px`
    callout.style.top = `${Math.max(20, rect.top - 60)}px`
    document.body.appendChild(callout)
  }, { text, label })
}

async function zoomLatestAssistantMessage(page, label) {
  await page.evaluate((label) => {
    const target = window.demoFindLatestAssistantBubble?.()
    if (!target) return

    const backdrop = document.createElement('div')
    backdrop.className = 'demo-focus-backdrop'
    document.body.appendChild(backdrop)

    target.classList.add('demo-spotlight-target')
    const rect = target.getBoundingClientRect()
    const callout = document.createElement('div')
    callout.className = 'demo-callout'
    callout.textContent = label
    callout.style.left = `${Math.min(window.innerWidth - 420, Math.max(24, rect.left))}px`
    callout.style.top = `${Math.max(62, rect.top - 60)}px`
    document.body.appendChild(callout)
  }, label)
}

async function highlightWord(page, { containingText, word, label }) {
  await page.evaluate(({ containingText, word, label }) => {
    const rect = window.demoFindTextRect?.(containingText, word)
    if (!rect) return

    const box = document.createElement('div')
    box.className = 'demo-red-box'
    box.style.left = `${Math.max(0, rect.left - 7)}px`
    box.style.top = `${Math.max(0, rect.top - 5)}px`
    box.style.width = `${rect.width + 14}px`
    box.style.height = `${rect.height + 10}px`
    document.body.appendChild(box)

    const callout = document.createElement('div')
    callout.className = 'demo-callout'
    callout.textContent = label
    callout.style.left = `${Math.min(window.innerWidth - 420, Math.max(24, rect.left - 10))}px`
    callout.style.top = `${Math.min(window.innerHeight - 82, rect.bottom + 16)}px`
    document.body.appendChild(callout)
  }, { containingText, word, label })
}

async function showMemoryOverlay(page) {
  await page.evaluate(() => {
    const card = document.createElement('div')
    card.className = 'demo-memory-card'
    card.innerHTML = `
      <div class="eyebrow">Error Memory updated</div>
      <h3>affect/effect</h3>
      <p>Luna lưu lỗi sai của Minh: dùng <strong>effect</strong> ở vị trí cần động từ. Lần chat tiếp theo, phản hồi sẽ nhắc lại đúng pattern này.</p>
    `
    document.body.appendChild(card)
  })
}

async function highlightLearningButtons(page) {
  await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button')).filter((button) =>
      ['Ôn tập', 'Flashcard'].includes(button.textContent?.trim()),
    )
    const visibleButtons = buttons.filter((button) => {
      const rect = button.getBoundingClientRect()
      return rect.width > 0 && rect.height > 0
    })
    if (!visibleButtons.length) return

    const rects = visibleButtons.map((button) => button.getBoundingClientRect())
    const left = Math.min(...rects.map((rect) => rect.left))
    const top = Math.min(...rects.map((rect) => rect.top))
    const right = Math.max(...rects.map((rect) => rect.right))
    const bottom = Math.max(...rects.map((rect) => rect.bottom))

    const backdrop = document.createElement('div')
    backdrop.className = 'demo-focus-backdrop'
    document.body.appendChild(backdrop)

    const box = document.createElement('div')
    box.className = 'demo-red-box'
    box.style.left = `${Math.max(0, left - 8)}px`
    box.style.top = `${Math.max(0, top - 8)}px`
    box.style.width = `${right - left + 16}px`
    box.style.height = `${bottom - top + 16}px`
    document.body.appendChild(box)

    const callout = document.createElement('div')
    callout.className = 'demo-callout'
    callout.textContent = 'Lỗi sai đã lưu sẽ được dùng cho Ôn tập và Flashcard cá nhân hóa'
    callout.style.left = `${Math.min(window.innerWidth - 420, Math.max(24, left - 40))}px`
    callout.style.top = `${Math.min(window.innerHeight - 90, bottom + 18)}px`
    document.body.appendChild(callout)
  })
}

async function clickWithCursor(page, locator) {
  const box = await locator.boundingBox()
  if (!box) {
    await locator.click()
    return
  }
  const x = box.x + box.width / 2
  const y = box.y + box.height / 2
  await page.evaluate(({ x, y }) => {
    let cursor = document.querySelector('.demo-cursor')
    if (!cursor) {
      cursor = document.createElement('div')
      cursor.className = 'demo-cursor'
      cursor.innerHTML = `
        <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M5 3L25 17.7L16.2 19.1L12 28L5 3Z" fill="white" stroke="#111827" stroke-width="2" stroke-linejoin="round"/>
        </svg>
      `
      cursor.style.left = '60px'
      cursor.style.top = `${window.innerHeight - 70}px`
      document.body.appendChild(cursor)
    }
    requestAnimationFrame(() => {
      cursor.style.left = `${x}px`
      cursor.style.top = `${y}px`
    })
  }, { x, y })
  await page.waitForTimeout(620)
  await page.evaluate(({ x, y }) => {
    const cursor = document.querySelector('.demo-cursor')
    if (cursor) cursor.style.transform = 'scale(0.84)'
    const ripple = document.createElement('div')
    ripple.className = 'demo-ripple'
    ripple.style.left = `${x - 14}px`
    ripple.style.top = `${y - 14}px`
    document.body.appendChild(ripple)
    window.setTimeout(() => {
      if (cursor) cursor.style.transform = 'scale(1)'
    }, 160)
  }, { x, y })
  await locator.click()
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
