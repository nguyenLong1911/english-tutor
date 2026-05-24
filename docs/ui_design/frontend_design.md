# Frontend Design Specification
## AI English Tutor — Personalized Learning with Long-Term Memory

> **Target readers:** Stitch, Codex, and any AI coding agent.  
> This document is the single source of truth for UI/UX implementation. Follow it precisely. Do not invent components or layouts not described here.

---

## 0. Design System

### 0.1 Aesthetic Direction

| Property | Value |
|---|---|
| **Theme** | Dark-first, deep navy + warm amber accent |
| **Tone** | Premium, calm, focused — like a personal study room at night |
| **Mood** | Trustworthy AI companion, not a gamified toy |
| **Differentiation** | Warm amber glow on key CTAs; soft teal for success/progress; generous whitespace inside a dark shell |

### 0.2 Color Tokens

```css
/* ── Brand ──────────────────────────────── */
--color-bg-base:        #0D1117;   /* page background */
--color-bg-surface:     #161B22;   /* card / panel surface */
--color-bg-elevated:    #1F2937;   /* hover, active, popover */
--color-bg-input:       #111827;   /* input fields */

/* ── Accent ──────────────────────────────── */
--color-amber:          #F59E0B;   /* primary CTA, highlights */
--color-amber-soft:     #FDE68A;   /* text on amber bg, hover glow */
--color-amber-dim:      #92400E;   /* subtle amber tint */

/* ── Semantic ────────────────────────────── */
--color-teal:           #14B8A6;   /* success, progress, correct */
--color-teal-dim:       #0F766E;
--color-red:            #F87171;   /* error, wrong answer */
--color-red-dim:        #7F1D1D;

/* ── Text ────────────────────────────────── */
--color-text-primary:   #F9FAFB;
--color-text-secondary: #9CA3AF;
--color-text-muted:     #4B5563;
--color-text-inverse:   #111827;   /* text on amber button */

/* ── Border ──────────────────────────────── */
--color-border:         #1F2937;
--color-border-hover:   #374151;
--color-border-focus:   #F59E0B;
```

### 0.3 Typography

```css
/* Display / Headings */
font-family: 'Fraunces', Georgia, serif;   /* emotional, literary feel */

/* Body / UI */
font-family: 'DM Sans', system-ui, sans-serif;

/* Code / vocabulary highlight */
font-family: 'JetBrains Mono', monospace;
```

**Google Fonts import:**
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,300;0,600;1,300&family=DM+Sans:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

**Scale:**

| Token | Size | Weight | Usage |
|---|---|---|---|
| `--text-display` | 56px | 300 | Landing hero headline |
| `--text-h1` | 36px | 600 | Page titles |
| `--text-h2` | 24px | 600 | Section headings |
| `--text-h3` | 18px | 500 | Card titles |
| `--text-body` | 15px | 400 | Body copy |
| `--text-small` | 13px | 400 | Labels, meta |
| `--text-mono` | 14px | 500 | Vocabulary, code |

### 0.4 Spacing & Layout

```css
--space-xs:   4px;
--space-sm:   8px;
--space-md:   16px;
--space-lg:   24px;
--space-xl:   40px;
--space-2xl:  64px;
--space-3xl:  96px;

--radius-sm:  6px;
--radius-md:  10px;
--radius-lg:  16px;
--radius-full: 9999px;

--shadow-glow: 0 0 20px rgba(245, 158, 11, 0.15);
--shadow-card: 0 1px 3px rgba(0,0,0,0.4);
```

### 0.5 Component Tokens

**Button — Primary (Amber)**
```css
background: var(--color-amber);
color: var(--color-text-inverse);
border: none;
border-radius: var(--radius-md);
padding: 12px 28px;
font-size: 15px;
font-weight: 500;
font-family: 'DM Sans';
cursor: pointer;
transition: box-shadow 0.2s, transform 0.1s;

/* hover */
box-shadow: var(--shadow-glow);
transform: translateY(-1px);
```

**Button — Ghost**
```css
background: transparent;
color: var(--color-text-secondary);
border: 1px solid var(--color-border);
border-radius: var(--radius-md);
padding: 10px 20px;

/* hover */
border-color: var(--color-border-hover);
color: var(--color-text-primary);
```

**Input Field**
```css
background: var(--color-bg-input);
border: 1px solid var(--color-border);
border-radius: var(--radius-md);
color: var(--color-text-primary);
padding: 12px 16px;
font-size: 15px;

/* focus */
border-color: var(--color-border-focus);
outline: none;
box-shadow: 0 0 0 3px rgba(245,158,11,0.1);
```

**Card**
```css
background: var(--color-bg-surface);
border: 1px solid var(--color-border);
border-radius: var(--radius-lg);
padding: var(--space-lg);
```

---

## 1. Landing Page (`/`)

### 1.1 Layout Overview

```
┌─────────────────────────────────────────────────┐
│  Navbar                                         │
├─────────────────────────────────────────────────┤
│  Hero Section                                   │
│  (headline + subheadline + CTA + preview image) │
├─────────────────────────────────────────────────┤
│  Features Section (4 cards)                     │
├─────────────────────────────────────────────────┤
│  How It Works / Workflow Section (3 steps)      │
├─────────────────────────────────────────────────┤
│  Social Proof / Quote                           │
├─────────────────────────────────────────────────┤
│  Final CTA Banner                               │
├─────────────────────────────────────────────────┤
│  Footer                                         │
└─────────────────────────────────────────────────┘
```

### 1.2 Navbar

- **Position:** `sticky top-0`, `z-index: 100`
- **Background:** `var(--color-bg-base)` + `backdrop-filter: blur(12px)` + `border-bottom: 1px solid var(--color-border)`
- **Content (flex row, space-between):**
  - **Left:** Logo — wordmark `Lingo·AI` in Fraunces italic 20px, amber dot between words
  - **Right:** Ghost button `Đăng nhập` + Primary button `Bắt đầu miễn phí`
- **Max-width:** 1200px, centered

### 1.3 Hero Section

- **Layout:** Two-column grid, 55% text / 45% visual
- **Background:** `var(--color-bg-base)` with subtle radial gradient centered behind headline: `radial-gradient(ellipse 800px 500px at 30% 50%, rgba(245,158,11,0.06) 0%, transparent 70%)`
- **Padding:** `var(--space-3xl)` top/bottom

**Left column — Text:**
```
[Eyebrow tag]   "Gia sư AI · Trí nhớ dài hạn"
                small, teal, letter-spacing 0.1em, uppercase

[Headline]      "Học tiếng Anh với
                gia sư nhớ mọi thứ
                về bạn."
                Fraunces, 56px, weight 300
                Line 1-2: --color-text-primary
                Line 3 "về bạn.": color --color-amber, italic

[Subheadline]   "Không phải app học từ vựng. Đây là gia sư cá nhân hoá
                hiểu nghề nghiệp, sở thích và lỗi lầm của bạn — 
                rồi dạy theo cách chỉ dành cho bạn."
                DM Sans, 17px, --color-text-secondary, max-width 480px, line-height 1.7

[CTA Row]       [Button Primary "Bắt đầu miễn phí →"]  [Ghost "Xem demo  ▶"]
                gap: 16px
```

**Right column — Visual:**
- Floating chat preview card (mock screenshot of app chat)
- Card: `var(--color-bg-surface)`, border, radius-lg, slight rotation `rotate(-2deg)`, `box-shadow: 0 32px 64px rgba(0,0,0,0.5)`
- Inside card: 3 chat bubbles alternating user/AI, last AI bubble shows amber-highlighted word correction
- Floating badge top-right of card: `"🧠 Nhớ 47 thông tin về bạn"` — teal background, small pill

### 1.4 Features Section

**Section header:**
```
Eyebrow: "Tính năng"
Title:   "Gia sư hiểu bạn từng ngày"
Subtext: short description
Alignment: center
```

**4 Feature Cards — grid 2×2, gap 24px, max-width 960px centered:**

| # | Icon (Lucide/Tabler) | Title | Description |
|---|---|---|---|
| 1 | `ti-message-dots` | Học qua đoạn chat | Không cần mở sách. Chỉ cần nhắn tin như chat với bạn bè — gia sư sẽ dạy theo ngữ cảnh thực. |
| 2 | `ti-user-circle` | Ghi nhớ thông tin cá nhân | Gia sư nhớ bạn làm gì, thích gì, ghét gì — để mọi ví dụ đều liên quan đến cuộc sống của bạn. |
| 3 | `ti-brain` | Ghi nhớ lỗi lầm | Mỗi lỗi ngữ pháp hay phát âm sai đều được ghi lại — và ôn lại đúng lúc bạn sắp quên. |
| 4 | `ti-refresh` | Nhắc lại gián đoạn | Spaced repetition thông minh. Ôn đúng thời điểm não bộ cần — không phải lịch cứng nhắc. |

**Card anatomy:**
```
[Icon 32px, amber]
[Title — DM Sans 18px, 500, text-primary]
[Description — 14px, text-secondary, line-height 1.6]
```
Card background: `var(--color-bg-surface)`, border: `var(--color-border)`, hover: border-color `var(--color-border-hover)` + `transform: translateY(-2px)`, transition 0.2s

### 1.5 Workflow Section — "Cách học hoạt động"

**Layout:** Horizontal 3-step row on desktop, vertical stack on mobile

**3 Steps:**

| Step | Icon | Label | Description |
|---|---|---|---|
| 01 | `ti-book-2` | Học qua bài giảng | Gia sư trình bày ngữ pháp, từ vựng, phát âm theo chủ đề phù hợp với trình độ và nghề nghiệp của bạn. |
| 02 | `ti-help-circle` | Ôn tập trả lời câu hỏi | Trả lời câu hỏi theo ngữ cảnh thực. Gia sư nhận xét tức thì, giải thích lý do đúng/sai. |
| 03 | `ti-cards` | Học qua Flashcard | Flashcard được tạo tự động từ những gì bạn đã học — ôn lại đúng lúc theo thuật toán nhớ lâu. |

**Step card styling:**
- Number badge: `01`, `02`, `03` — Fraunces, 48px, weight 300, color `var(--color-amber)` at 20% opacity (decorative background)
- Connector arrow between steps: `→` icon, `var(--color-border-hover)`
- Active/hover: left border `3px solid var(--color-amber)`

### 1.6 Social Proof

Single large quote block, centered, max-width 640px:
```
"   "
[Quote text — Fraunces italic 22px, text-secondary]
[Author name — DM Sans 14px, teal]
[Author role — DM Sans 13px, text-muted]
```
Decorative large amber `"` quotation mark behind text.

### 1.7 Final CTA Banner

Dark amber gradient strip:
```css
background: linear-gradient(135deg, #1C1407 0%, #2D1F00 100%);
border: 1px solid var(--color-amber-dim);
border-radius: var(--radius-lg);
```
Content: headline + subtext + Primary CTA button, all centered.

### 1.8 Footer

Simple two-row footer:
- Row 1: Logo left, links right (`Tính năng`, `Giá cả`, `Blog`, `Liên hệ`)
- Row 2: Copyright left, social icons right (Twitter/X, LinkedIn) using Tabler icons

---

## 2. Login / Signup Page (`/auth`)

### 2.1 Layout

Full-screen split layout, `min-height: 100vh`:

```
┌──────────────────────┬──────────────────────────┐
│  Left Panel 45%      │  Right Panel 55%          │
│  (branding / quote)  │  (auth form)              │
└──────────────────────┴──────────────────────────┘
```

### 2.2 Left Panel

- **Background:** `var(--color-bg-surface)` with radial amber glow bottom-left
- **Content (vertically centered, padding 60px):**
  - Logo `Lingo·AI` — Fraunces 24px
  - Tagline below logo — italic, text-secondary
  - Large decorative quote (same as 1.6 style)
  - Bottom strip: 3 micro-features in a row (`🧠 Trí nhớ dài hạn`, `📚 3 hình thức học`, `🎯 Cá nhân hoá`)

### 2.3 Right Panel

- **Background:** `var(--color-bg-base)`
- **Content (vertically centered, max-width 400px, centered horizontally):**

**Tab switcher** (Đăng nhập / Đăng ký) — pill tabs, active tab gets amber underline:
```css
.tab-active {
  color: var(--color-amber);
  border-bottom: 2px solid var(--color-amber);
}
```

**Login form fields:**
1. Email input (label: `Email`)
2. Password input (label: `Mật khẩu`) + show/hide toggle icon right
3. Row: `Quên mật khẩu?` link right-aligned (amber, 13px)
4. Primary button full-width: `Đăng nhập`
5. Divider: `─── hoặc ───`
6. Ghost button full-width with Google icon: `Tiếp tục với Google`

**Signup form fields (shown when tab = Đăng ký):**
1. Full name input
2. Email input
3. Password input + strength indicator bar (4 segments, teal when strong)
4. Primary button: `Tạo tài khoản`
5. Divider + Google button (same as login)
6. Terms text below: small, muted

**Form validation states:**
- Error: border-color `var(--color-red)`, small error text below in red
- Success: border-color `var(--color-teal)`, check icon inside input right

---

## 3. Onboarding — Initial Questions Page (`/onboarding`)

### 3.1 Layout

Single column, centered, `max-width: 640px`, full-screen with progress bar at top.

```
┌─────────────────────────────────────────────────┐
│  [Progress bar top — full width]                │
│                                                 │
│  Step X / 6                                     │
│  Question headline                              │
│  Question subtext                               │
│                                                 │
│  [Answer options / input]                       │
│                                                 │
│  [Back]  [Tiếp tục →]                          │
└─────────────────────────────────────────────────┘
```

### 3.2 Progress Bar

```css
/* Track */
height: 3px;
background: var(--color-bg-elevated);
width: 100%;
position: fixed;
top: 0;

/* Fill */
background: var(--color-amber);
transition: width 0.4s ease;
```

### 3.3 Step Counter & Navigation

- Step label: `Câu hỏi 1/6` — DM Sans 13px, teal, uppercase, letter-spacing
- Back button: ghost, left arrow icon, hidden on step 1
- Continue button: primary amber, disabled state if no answer selected

**Disabled button state:**
```css
opacity: 0.4;
cursor: not-allowed;
box-shadow: none;
```

### 3.4 Six Questions

**Q1 — Trình độ hiện tại**
- Type: single-select cards (grid 2×2)
- Options: `Mới bắt đầu`, `Cơ bản (A2)`, `Trung cấp (B1-B2)`, `Nâng cao (C1+)`
- Card selected state: `border: 1.5px solid var(--color-amber)`, `background: rgba(245,158,11,0.08)`

**Q2 — Nghề nghiệp**
- Type: tag chips (multi-select, can pick 1)
- Options: `Kỹ sư / Developer`, `Kinh doanh / Sales`, `Marketing`, `Thiết kế`, `Y tế`, `Giáo dục`, `Tài chính`, `Khác`
- Chip selected: amber border + amber text

**Q3 — Sở thích**
- Type: tag chips multi-select (up to 3)
- Options: `Công nghệ`, `Du lịch`, `Thể thao`, `Âm nhạc`, `Phim ảnh`, `Ẩm thực`, `Đọc sách`, `Game`, `Thời trang`, `Khoa học`
- Hint text below: `Chọn tối đa 3 chủ đề bạn thích nhất`

**Q4 — Mục tiêu học tập**
- Type: single-select cards (vertical list), each with icon + title + description

| Option | Icon | Description |
|---|---|---|
| Giao tiếp hàng ngày | `ti-message-circle` | Nói chuyện tự tin với người nước ngoài |
| Công việc & Email | `ti-briefcase` | Viết email, thuyết trình, họp quốc tế |
| Thi cử (IELTS/TOEIC) | `ti-certificate` | Chuẩn bị cho kỳ thi cụ thể |
| Du học / Định cư | `ti-plane` | Chuẩn bị cho môi trường nước ngoài |

**Q5 — Phong cách học**
- Type: single-select cards 2×2

| Option | Icon |
|---|---|
| Giải thích chi tiết, có lý do | `ti-book` |
| Ngắn gọn, đi thẳng vào vấn đề | `ti-bolt` |
| Nhiều ví dụ thực tế | `ti-bulb` |
| Sửa lỗi ngay lập tức | `ti-pencil` |

**Q6 — Thời gian học mỗi ngày**
- Type: single-select chips
- Options: `5 phút`, `10 phút`, `20 phút`, `30 phút`, `60 phút+`

### 3.5 Final Screen (after Q6)

Animated completion screen:
```
[Large checkmark animation — teal, scale in]
"Tuyệt vời! Gia sư của bạn đã sẵn sàng."
[Subtext: personalised summary — e.g. "Dựa trên thông tin của bạn, gia sư sẽ dạy tiếng Anh công nghệ qua hội thoại ngắn gọn..."]
[Button: "Bắt đầu học ngay →"]
```

---

## 4. Main App Page (`/app`)

### 4.1 Overall Layout — Three-Column Shell

```
┌──────────┬──────────────────────────┬──────────────────┐
│  Navbar  │                          │                  │
│  Left    │    Chat Area             │   Content Panel  │
│  240px   │    (flex 1)              │   320px          │
│          │                          │   (collapsible)  │
└──────────┴──────────────────────────┴──────────────────┘
```

- **Total layout:** `display: flex; height: 100vh; overflow: hidden;`
- **Left navbar:** `240px` fixed, collapsible to `64px` (icon-only mode)
- **Chat area:** `flex: 1`, `min-width: 0`
- **Right content panel:** `320px` fixed, collapsible to `0` (hidden), slide animation

### 4.2 Left Navbar

**Background:** `var(--color-bg-surface)`, `border-right: 1px solid var(--color-border)`

**Top section:**
- Logo `Lingo·AI` (hidden when collapsed → show only amber dot icon)
- Collapse toggle button: `ti-layout-sidebar-left-collapse` / `ti-layout-sidebar-left-expand`

**Navigation items** (icon + label, label hidden when collapsed):

| Icon | Label | Route hint |
|---|---|---|
| `ti-message` | Chat với gia sư | Active state |
| `ti-book-2` | Bài giảng | |
| `ti-cards` | Flashcard | |
| `ti-help-circle` | Ôn tập | |
| `ti-chart-bar` | Tiến độ | |

**Nav item styling:**
```css
/* default */
display: flex; align-items: center; gap: 12px;
padding: 10px 16px;
border-radius: var(--radius-md);
color: var(--color-text-secondary);

/* hover */
background: var(--color-bg-elevated);
color: var(--color-text-primary);

/* active */
background: rgba(245,158,11,0.1);
color: var(--color-amber);
border-left: 2px solid var(--color-amber);
```

**Bottom section of navbar:**
- User avatar (initials circle, 32px, amber bg)
- Username (hidden when collapsed)
- `ti-settings` icon → settings

**Memory chip** (above bottom user section):
- Small card: `🧠 47 ký ức · Tuần này +3`
- Background: `rgba(20, 184, 166, 0.1)`, teal border, teal text
- Hidden when navbar collapsed

### 4.3 Chat Area (Center)

**Background:** `var(--color-bg-base)`

**Header bar:**
```
[AI Avatar 36px]  "Luna — Gia sư AI của bạn"  [status: ● Đang hoạt động]
                                               [Right: btn "Bài giảng" | "Ôn tập" | "Flashcard"]
```
Right buttons toggle the content panel and set its mode. Active button: amber.

**Message list** — `flex: 1; overflow-y: auto; padding: 24px`

**User message bubble:**
```css
align-self: flex-end;
max-width: 70%;
background: var(--color-bg-elevated);
border-radius: 16px 16px 4px 16px;
padding: 12px 16px;
color: var(--color-text-primary);
```

**AI message bubble:**
```css
align-self: flex-start;
max-width: 75%;
background: var(--color-bg-surface);
border: 1px solid var(--color-border);
border-radius: 16px 16px 16px 4px;
padding: 12px 16px;
```

**AI message — special inline components:**
- **Vocabulary highlight:** inline `<span>` with amber underline + tooltip on hover showing translation
- **Error correction:** red strikethrough old text → teal corrected text with `ti-arrow-right` between
- **Grammar note card:** embedded in AI bubble, slightly inset card with amber left border
- **"Nhớ lại" badge:** `🔁 Lỗi lặp lại từ tuần trước` — small pill, amber, appears above relevant correction

**Typing indicator:** three animated dots, `var(--color-text-muted)`

**Input area** — `border-top: 1px solid var(--color-border)`, padding 16px:
```
[Textarea: placeholder "Nhắn tin với gia sư..." — auto-expand, max 4 rows]
[Right side row: ti-microphone ghost btn | ti-send primary btn 36px]
```
Textarea: no border, background `var(--color-bg-surface)`, border-radius `var(--radius-md)`, full-width

**Keyboard shortcut hint:** `Enter để gửi · Shift+Enter xuống dòng` — 11px, muted, below input

### 4.4 Right Content Panel

**Background:** `var(--color-bg-surface)`, `border-left: 1px solid var(--color-border)`
**Width:** 320px, `transition: width 0.25s ease`
**Collapse:** slides to `width: 0; overflow: hidden`

**Panel header:**
```
[Current mode title]          [ti-x close button]
```
Mode title changes based on active content: `Bài giảng`, `Ôn tập`, or `Flashcard`

---

#### Mode A: Bài giảng (Lesson)

Layout — scrollable vertical:
```
[Lesson chip tag: "Ngữ pháp · Present Perfect"]
[Lesson title — Fraunces 20px]
[Progress bar: Bài 3/8]

[Section: "Giải thích"]
[Body text with highlighted examples]
[Vocabulary list — DM Mono, amber]

[Section: "Ví dụ"]
[3 example sentences — numbered, teal bullets]

[CTA: "Bắt đầu ôn tập →" — full-width primary]
```

#### Mode B: Ôn tập — Trả lời câu hỏi (Q&A)

```
[Question counter: "Câu 2/5"]
[Question text — 18px, text-primary]
[Subcontext — italic, text-secondary, 14px]

[Answer input textarea or multiple choice]

[Submit button "Kiểm tra đáp án"]

━━━ [Result section — revealed after submit] ━━━
[✓ Đúng! / ✗ Sai] — teal/red with icon
[Explanation block — amber left border]
[Next question button]
```

Multiple choice option styling:
```css
/* default */
border: 1px solid var(--color-border);
border-radius: var(--radius-md);
padding: 12px;

/* selected — before reveal */
border-color: var(--color-amber);
background: rgba(245,158,11,0.06);

/* correct reveal */
border-color: var(--color-teal);
background: rgba(20,184,166,0.08);

/* incorrect reveal */
border-color: var(--color-red);
background: rgba(248,113,113,0.08);
```

#### Mode C: Flashcard

```
[Counter: "12/30 flashcards"]
[Progress dots row — filled = reviewed]

[Card — large, centered, flip-able]
  Front: [English word/phrase — Fraunces 28px]
         [Context sentence — italic, small]
  Back:  [Vietnamese meaning — 24px]
         [Example usage — 14px]
         [Memory tag: "Lần đầu gặp" / "Đã quên 2 lần"]

[Flip button: "Lật thẻ ↻"]

[After flip — 3 rating buttons:]
  [Không nhớ] [Gần nhớ] [Nhớ rõ]
   red ghost    amber      teal
```

Card flip animation:
```css
.flashcard {
  transform-style: preserve-3d;
  transition: transform 0.4s ease;
}
.flashcard.flipped {
  transform: rotateY(180deg);
}
.flashcard-front, .flashcard-back {
  backface-visibility: hidden;
}
.flashcard-back {
  transform: rotateY(180deg);
}
```

---

## 5. Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| `≥ 1280px` | Full 3-column layout |
| `960–1279px` | Right panel auto-collapsed by default, toggled via button |
| `768–959px` | Left navbar collapsed to icon-only (64px) |
| `< 768px` | Bottom tab bar replaces left navbar; right panel = full-screen drawer overlay |

### Mobile Bottom Tab Bar (< 768px)

Fixed bottom, `height: 56px`, `background: var(--color-bg-surface)`, top border:
- 4 tabs: Chat · Học · Flashcard · Tiến độ
- Active: amber icon + amber label
- Inactive: muted icon, no label

---

## 6. Micro-interactions & Animation Checklist

| Element | Animation |
|---|---|
| Page load | Staggered fade-up: hero text lines `animation-delay: 0.1s, 0.2s, 0.3s` |
| Feature cards | Fade-up on scroll-into-view (`IntersectionObserver`) |
| Chat message in | `opacity: 0 → 1` + `translateY(8px → 0)`, 200ms |
| AI typing indicator | 3 dots pulse `scale(1 → 1.3 → 1)` staggered 150ms |
| Onboarding step transition | Slide-left on next, slide-right on back, 250ms |
| Card selection | Scale `1 → 0.98 → 1` on click, 100ms |
| Flashcard flip | `rotateY` 400ms ease |
| Right panel open/close | `width` transition 250ms ease |
| Navbar collapse | `width` transition 200ms ease |
| Button hover | `translateY(-1px)` + glow shadow |
| Success answer | Teal pulse ring from border, 400ms |

---

## 7. File & Component Structure Recommendation

```
src/
├── pages/
│   ├── LandingPage.jsx
│   ├── AuthPage.jsx
│   ├── OnboardingPage.jsx
│   └── AppPage.jsx
│
├── components/
│   ├── layout/
│   │   ├── Navbar.jsx          # landing page top nav
│   │   ├── AppShell.jsx        # 3-column layout wrapper
│   │   ├── LeftNav.jsx         # collapsible left sidebar
│   │   └── RightPanel.jsx      # collapsible content panel
│   │
│   ├── chat/
│   │   ├── ChatArea.jsx
│   │   ├── MessageBubble.jsx   # user + AI variants
│   │   ├── ChatInput.jsx
│   │   └── TypingIndicator.jsx
│   │
│   ├── content/
│   │   ├── LessonView.jsx
│   │   ├── QuizView.jsx
│   │   └── FlashcardView.jsx
│   │
│   ├── onboarding/
│   │   ├── StepCard.jsx        # question wrapper
│   │   ├── OptionCard.jsx      # selectable card option
│   │   └── TagChip.jsx         # multi-select chip
│   │
│   └── ui/
│       ├── Button.jsx
│       ├── Input.jsx
│       ├── ProgressBar.jsx
│       └── MemoryChip.jsx
│
├── styles/
│   └── tokens.css              # all CSS variables from Section 0
│
└── assets/
    └── fonts.css               # Google Fonts import
```

---

## 8. Copy & Content Defaults (Vietnamese)

All UI text defaults to Vietnamese. English terms in content (lesson titles, vocabulary) remain in English.

| Element | Default copy |
|---|---|
| App name | `Lingo·AI` |
| AI tutor name | `Luna` |
| AI status | `Đang hoạt động` |
| Chat placeholder | `Nhắn tin với gia sư...` |
| Empty chat | `Chào bạn! Tôi là Luna, gia sư AI của bạn. Hôm nay bạn muốn học gì?` |
| Loading AI | `Luna đang suy nghĩ...` |
| Memory chip | `🧠 {n} ký ức · Tuần này +{m}` |
| Onboarding title | `Hãy để tôi hiểu bạn hơn` |
| Onboarding subtitle | `Chỉ mất 2 phút · Càng trả lời đúng, học càng hiệu quả` |

---

*End of specification. Implement all sections exactly as described. Use the design tokens from Section 0 throughout — do not introduce new color values or font families.*
