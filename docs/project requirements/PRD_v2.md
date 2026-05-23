# PRODUCT REQUIREMENTS DOCUMENT
# Agentic Language Tutor — Trợ Lý Học Ngoại Ngữ Trí Nhớ Dài Hạn

| Phiên bản | Mô tả | Ngày | Bảo mật |
|---|---|---|---|
| v2.0 — Enhanced | PRD mở rộng: User Stories, Wireframes, Creative Features | Tháng 4, 2025 | Nội bộ |
| Chủ sở hữu | Agentic Tutor Team | — | — |

---

## Mục lục

1. [Tóm Tắt Điều Hành](#1-tóm-tắt-điều-hành)
2. [Bối Cảnh & Mục Tiêu](#2-bối-cảnh--mục-tiêu)
3. [User Persona](#3-user-persona)
4. [Problem Statement](#4-problem-statement)
5. [Phạm Vi Sản Phẩm](#5-phạm-vi-sản-phẩm)
6. [User Stories — Đúng Format Sư Phạm](#6-user-stories--đúng-format-sư-phạm)
7. [Functional Requirements: Core vs Nice-to-Have](#7-functional-requirements-core-vs-nice-to-have)
8. [Wireframes & Mockups](#8-wireframes--mockups)
9. [💡 Tính Năng Sáng Tạo — Những Thứ Chưa Được Nói Đến](#9--tính-năng-sáng-tạo--những-thứ-chưa-được-nói-đến)
10. [Kiến Trúc Kỹ Thuật](#10-kiến-trúc-kỹ-thuật)
11. [Non-Functional Requirements](#11-non-functional-requirements)
12. [Phân Tích Đối Thủ & Định Vị](#12-phân-tích-đối-thủ--định-vị)
13. [Roadmap Alpha — 6 Tuần](#13-roadmap-alpha--6-tuần)
14. [Metrics & KPIs](#14-metrics--kpis)
15. [Rủi Ro & Giảm Thiểu](#15-rủi-ro--giảm-thiểu)
16. [Phụ Lục](#16-phụ-lục)

---

## 1. Tóm Tắt Điều Hành

Agentic Language Tutor là nền tảng học ngoại ngữ thế hệ mới cho người đi làm bận rộn (18–35 tuổi). Ba vấn đề cốt lõi cần giải quyết: duy trì mạch kiến thức xuyên phiên học ngắt quãng, cá nhân hóa sâu theo hồ sơ lỗi sai, và áp dụng kiến thức vào công việc thực tế.

Kiến trúc ba tầng: **Mem0** (bộ nhớ dài hạn) + **LangGraph** (điều phối luồng gia sư) + **Claude/GPT-4o** (xử lý ngôn ngữ). Alpha test: 100–200 người dùng trong 6 tuần.

| Mục tiêu | Phạm vi alpha | Chỉ số thành công |
|---|---|---|
| Giảm churn từ 48% → dưới 30% | 100–200 người dùng | Retention D7 ≥ 40%, D30 ≥ 25% |
| Trí nhớ cá nhân hóa xuyên phiên | 50–100 lượt hội thoại/tuần | Accuracy +26% (Mem0 benchmark) |
| Giảm 90% chi phí token | 1,000–2,000 facts/user | Truy xuất < 1 giây |

---

## 2. Bối Cảnh & Mục Tiêu

### 2.1 Bối cảnh thị trường

Nhóm nhân viên văn phòng và sinh viên năm cuối (18–35 tuổi) chiếm **48%** thị trường học ngôn ngữ số. Họ học theo mô hình micro-learning (17–23 phút/ngày), học ngắt quãng thường xuyên.

Điểm mù của giải pháp hiện tại: không duy trì bộ nhớ chi tiết qua các phiên, gây **"Context Drift"** (hiệu năng AI giảm 39% khi hội thoại dài) và **"Bệnh Quên"** buộc người học làm lại từ đầu mỗi phiên.

### 2.2 Mục tiêu sản phẩm

- **Kinh doanh:** D30 retention ≥ 25%, churn < 30% quý đầu.
- **Sư phạm:** Lộ trình học dựa trên hồ sơ lỗi sai lâu dài, không phải session-based.
- **Kỹ thuật:** Mem0 + LangGraph, truy xuất < 1 giây, token cost giảm 90%.
- **Alpha:** Tinh chỉnh thuật toán cá nhân hóa với dữ liệu thực.

---

## 3. User Persona

### 3.1 Persona chính

| Thuộc tính | Chi tiết |
|---|---|
| **Tên đại diện** | Minh — Nhân viên Marketing 27 tuổi |
| **Thời gian học** | 17–23 phút/ngày (xe bus, giờ trưa, trước khi ngủ) |
| **Mục tiêu** | Thăng tiến công việc, phỏng vấn quốc tế, đọc tài liệu chuyên ngành |
| **Nỗi đau** | Học xong quên ngay; AI không nhớ lỗi cũ; bài tập không liên quan công việc |
| **Hành vi** | Dùng Duolingo cho streak + ChatGPT cho hỏi đáp, không có công cụ tích hợp |

### 3.2 Ba trạng thái học tập cần nhận diện

| Trạng thái | Ký hiệu | Biểu hiện | Phản hồi AI |
|---|---|---|---|
| Bệnh Quên | 🟡 YELLOW | Quên từ vựng, lỗi cũ tái diễn | Spaced Repetition, nhắc lại có ngữ cảnh |
| Bệnh Nghẽn | 🔴 RED | Kiến thức không áp dụng được | Bài tập tình huống thực tế theo ngành |
| Bao che lỗi | 🔵 BLUE | AI bỏ qua lỗi để hội thoại trơn tru | Scaffolding: gợi ý sửa lỗi, không cho đáp án thẳng |

---

## 4. Problem Statement

> **Core Problem:** Người đi làm bận rộn gặp khó khăn duy trì mạch kiến thức và cá nhân hóa lộ trình trong bối cảnh học ngoại ngữ ngắt quãng qua ứng dụng di động.

**Nguyên nhân gốc rễ:**
- **Session-based architecture:** Hệ thống "quên sạch" profile chi tiết khi đóng app — không biết người dùng tiến bộ thế nào sau 6 tháng.
- **Context Drift:** Hiệu năng AI giảm 39% khi hội thoại kéo dài *(LLMs Get Lost In Multi-Turn Conversation).*
- **One-size-fits-all:** Không cá nhân hóa theo hồ sơ lỗi sai lâu dài → bài tập "cào bằng".
- **Thiếu liên kết thực tế:** Kiến thức không gắn với ngữ cảnh công việc → Bệnh Nghẽn → churn 48%.

---

## 5. Phạm Vi Sản Phẩm

### ✅ IN SCOPE — Alpha v1.0
- Persistent Memory với Mem0 (cross-session)
- Hồ sơ lỗi sai tích lũy theo thời gian
- Scaffolding tutoring via LangGraph (4-node pipeline)
- Hội thoại tự nhiên text-based
- Spaced Repetition tự động (SM-2)
- Web app mobile-responsive
- API: OpenAI + Mem0 + LangGraph

### ❌ OUT OF SCOPE — Future Releases
- Native iOS/Android app
- Gamification (streak, leaderboard)
- Voice/pronunciation assessment
- Hệ thống thanh toán & subscription
- Custom AI model training
- Đa ngôn ngữ (ngoài tiếng Anh)

---

## 6. User Stories — Đúng Format Sư Phạm

> Format chuẩn: **"Là [role], tôi muốn [action] để [benefit]"** — viết cho từng loại user.

---

### 6.1 👤 Người học mới (New Learner)

**US-N01** | Priority: 🔴 P0
> *"Là người học mới, tôi muốn hoàn thành onboarding trong vòng 3 phút để bắt đầu học ngay mà không cảm thấy bị cản trở."*

**Acceptance Criteria:**
- Onboarding gồm đúng 3 bước: trình độ (A1–C1) → ngành nghề → mục tiêu
- Không có bước đăng ký phức tạp (email + password là đủ)
- Bài học đầu tiên được generate ngay sau khi hoàn thành, không cần chờ

---

**US-N02** | Priority: 🔴 P0
> *"Là người học mới, tôi muốn AI giới thiệu bản thân và giải thích nó sẽ nhớ gì về tôi, để tôi tin tưởng chia sẻ thông tin thật."*

**Acceptance Criteria:**
- Màn hình Welcome nêu rõ: "Tôi sẽ nhớ lỗi sai của bạn, không bao giờ hỏi lại điều bạn đã học"
- Link tới Privacy Policy hiển thị nổi bật
- Người dùng có thể xóa toàn bộ memory bất kỳ lúc nào từ Settings

---

### 6.2 👤 Người học thường xuyên (Regular Learner)

**US-R01** | Priority: 🔴 P0
> *"Là người học thường xuyên, tôi muốn AI nhớ lỗi sai của tôi từ phiên trước và tự động nhắc lại, để tôi không phải giải thích lại từ đầu mỗi khi mở app."*

**Acceptance Criteria:**
- AI chủ động nhắc lỗi sai trong vòng 3 phiên tiếp theo, kèm ngữ cảnh cụ thể ("Tuần trước bạn đã nhầm 'affect' với 'effect'...")
- Không cần người dùng yêu cầu — hệ thống tự trigger
- Nhắc lại có thể được hoãn nếu người dùng đang học nội dung khác

---

**US-R02** | Priority: 🔴 P0
> *"Là người học thường xuyên, tôi muốn AI không cho đáp án ngay mà gợi ý từng bước, để tôi có cơ hội tự suy nghĩ và nhớ lâu hơn."*

**Acceptance Criteria:**
- AI đưa ra tối thiểu 2 hints trước khi reveal đáp án
- Không cho đáp án trong 60 giây đầu kể từ khi câu hỏi được đặt ra
- Người dùng có thể gõ "give up" để nhận đáp án ngay (escape hatch)

---

**US-R03** | Priority: 🟡 P1
> *"Là người học thường xuyên, tôi muốn xem bảng tóm tắt tiến độ hàng tuần, để biết mình đang cải thiện ở đâu và còn yếu điểm gì."*

**Acceptance Criteria:**
- Dashboard hiển thị: top 5 lỗi sai thường gặp, số từ mới học, accuracy rate theo tuần
- Dữ liệu được tổng hợp tự động, không cần người dùng nhập thêm
- Biểu đồ đường cho accuracy trend trong 30 ngày

---

**US-R04** | Priority: 🟡 P1
> *"Là người học thường xuyên, tôi muốn AI tự động điều chỉnh độ khó khi tôi tiến bộ, để tôi không bị nhàm khi đã thành thạo một mảng kiến thức."*

**Acceptance Criteria:**
- Độ khó tăng tự động khi accuracy > 80% trong 3 phiên liên tiếp
- Người dùng nhận thông báo nhỏ: "Bạn đã thành thạo [topic], chuyển sang mức tiếp theo!"
- Có thể quay về mức cũ nếu người dùng muốn ôn lại

---

### 6.3 👤 Người học bận rộn (Busy Learner — micro-learning mode)

**US-B01** | Priority: 🔴 P0
> *"Là người đi làm bận rộn, tôi muốn có thể học có ích trong 5–10 phút bất kỳ lúc nào, để không lãng phí những khoảng thời gian nhỏ trong ngày."*

**Acceptance Criteria:**
- Khi mở app, hệ thống hiển thị ngay "Bài ôn hôm nay" (tối đa 5 thẻ từ/1 mini-exercise)
- Session có thể bị ngắt bất cứ lúc nào — tiến độ được lưu tự động
- Không có màn hình loading dài hơn 2 giây

---

**US-B02** | Priority: 🟡 P1
> *"Là người đi làm bận rộn, tôi muốn bài tập được gắn với tình huống công việc thực tế của tôi, để kiến thức có thể áp dụng ngay ngày mai."*

**Acceptance Criteria:**
- Tối thiểu 60% bài tập sử dụng từ vựng và tình huống thuộc ngành nghề đã chọn khi onboarding
- Ví dụ: người dùng chọn Marketing → bài tập về email marketing, pitch deck, A/B testing
- Người dùng có thể đổi ngành nghề trong Settings

---

### 6.4 👤 Admin / Nhóm nghiên cứu (Internal)

**US-A01** | Priority: 🟡 P1
> *"Là thành viên nhóm phát triển, tôi muốn xem dashboard kỹ thuật theo dõi chi phí token theo user và session, để kiểm soát ngân sách API trong giai đoạn alpha."*

**Acceptance Criteria:**
- Dashboard nội bộ hiển thị: avg token/session, cost/user/ngày, tổng chi phí tuần
- Cảnh báo khi một user vượt 50 queries/ngày (rate limit)
- Export CSV cho báo cáo hàng tuần

---

## 7. Functional Requirements: Core vs Nice-to-Have

> Phân loại theo mức độ bắt buộc để đội kỹ thuật ưu tiên triển khai trong 6 tuần alpha.

---

### 🔴 CORE — Bắt buộc (Must Have cho Alpha)

| # | Tính năng | Mô tả chi tiết | Độ phức tạp |
|---|---|---|---|
| C-01 | **Persistent Memory (Mem0)** | Lưu tối thiểu 5 loại facts/user: lỗi ngữ pháp, từ vựng chưa nắm, chủ đề, ngành nghề, trình độ. Tối đa 1,000–2,000 facts/user trong vector DB. Latency P95 < 1s. | 🔴 Cao |
| C-02 | **LangGraph 4-Node Pipeline** | Memory Retrieval → Context Builder → Scaffolding Engine → Memory Writer. End-to-end < 3s. Phân biệt 3 intent: luyện tập / hỏi đáp nhanh / kiểm tra tiến độ. | 🔴 Cao |
| C-03 | **Scaffolding Engine** | Phát hiện lỗi sai → tối thiểu 2 hints → reveal đáp án sau 60s. Không "bao che" (🔵). Tone feedback tích cực, có giải thích nguyên nhân. | 🟡 Trung bình |
| C-04 | **Spaced Repetition (SM-2)** | Lịch nhắc lại tự động theo hiệu suất: đúng → giãn interval; sai → reset. Hiển thị "từ cần ôn hôm nay" khi mở app. | 🟡 Trung bình |
| C-05 | **Onboarding Flow** | 3 bước: trình độ → ngành nghề → mục tiêu. Hoàn thành < 3 phút. Profile được dùng ngay từ phiên đầu tiên. | 🟢 Thấp |
| C-06 | **Chat Interface (Mobile-Responsive)** | Text-based conversation UI. Session auto-save. Loading < 2s. Escape hatch "give up" để nhận đáp án. | 🟢 Thấp |
| C-07 | **Delete My Data** | Người dùng xóa toàn bộ memory trong < 30 giây. Tuân thủ GDPR cơ bản. PII scrubbing trước khi lưu vào Mem0. | 🟢 Thấp |

---

### 🟡 NICE-TO-HAVE — Nên có (Triển khai nếu còn thời gian)

| # | Tính năng | Mô tả chi tiết | Ghi chú |
|---|---|---|---|
| N-01 | **Progress Dashboard** | Top 5 lỗi sai/30 ngày, accuracy chart, streak counter. | Có thể dùng bản đơn giản trước |
| N-02 | **Adaptive Difficulty** | Tự động tăng độ khó khi accuracy > 80% trong 3 phiên. Thông báo tiến độ. | Cần đủ data trước khi bật |
| N-03 | **Industry-Specific Content** | ≥ 60% bài tập dùng từ vựng ngành nghề người dùng chọn. Đổi ngành được trong Settings. | Content work, không phải tech |
| N-04 | **Internal Admin Dashboard** | Token cost monitoring, rate limit alerts, CSV export. | Cần từ Sprint 1 để quản lý chi phí |
| N-05 | **Memory Compression** | Tự động merge facts trùng và giảm importance_score facts cũ khi vượt 2,000. | Chỉ cần khi user đạt ngưỡng |
| N-06 | **Weekly Progress Email** | Tóm tắt tuần: số từ học, lỗi nổi bật, gợi ý cho tuần tới. | Giúp re-engagement |

---

### ⚪ P2 — Bỏ qua trong Alpha

| # | Tính năng | Lý do hoãn |
|---|---|---|
| P2-01 | Export PDF báo cáo tháng | Không đủ thời gian, ít impact ngay giai đoạn alpha |
| P2-02 | Gamification (streak, badge) | Cần design system riêng, out of scope 6 tuần |
| P2-03 | Voice/Pronunciation | Cần model riêng, infrastructure phức tạp |
| P2-04 | Multi-language support | Tập trung sâu một ngôn ngữ trước |

---

## 8. Wireframes & Mockups

> Sketch giao diện chính ở dạng text wireframe. Dùng làm reference cho Figma/Excalidraw.

---

### 8.1 Screen 1: Onboarding Flow

```
┌─────────────────────────────────────┐
│  🎓 Agentic Tutor                   │
│  Bước 1 / 3 ──────────────────────  │
│                                     │
│  Trình độ tiếng Anh của bạn?        │
│                                     │
│  ┌────────┐  ┌────────┐  ┌────────┐ │
│  │  A1    │  │  A2    │  │  B1    │ │
│  │ Mới bắt│  │ Cơ bản │  │ Trung  │ │
│  │  đầu  │  │        │  │  cấp   │ │
│  └────────┘  └────────┘  └────────┘ │
│                                     │
│  ┌────────┐  ┌────────┐             │
│  │  B2    │  │  C1    │             │
│  │ Khá    │  │ Nâng   │             │
│  │        │  │  cao   │             │
│  └────────┘  └────────┘             │
│                                     │
│  [Tiếp tục →]                       │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  🎓 Agentic Tutor                   │
│  Bước 2 / 3 ──────────────────────  │
│                                     │
│  Bạn làm việc trong lĩnh vực nào?  │
│                                     │
│  ○ 💻 Technology & IT               │
│  ○ 📈 Marketing & Sales             │
│  ○ 💰 Finance & Banking             │
│  ○ 🏥 Healthcare                    │
│  ○ 📚 Education                     │
│  ○ ✏️ Khác (nhập tay)              │
│                                     │
│  [← Quay lại]   [Tiếp tục →]       │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  🎓 Agentic Tutor                   │
│  Bước 3 / 3 ──────────────────────  │
│                                     │
│  Mục tiêu học của bạn là gì?        │
│                                     │
│  ☐ Phỏng vấn xin việc quốc tế      │
│  ☐ Giao tiếp công việc hàng ngày   │
│  ☐ Đọc tài liệu chuyên ngành       │
│  ☐ Thi chứng chỉ (IELTS, TOEIC...) │
│                                     │
│  ────────────────────────────────── │
│  ✅ Tôi sẽ nhớ lỗi sai của bạn và  │
│     không bao giờ hỏi lại điều đã  │
│     học. [Xem Privacy Policy]       │
│                                     │
│  [Bắt đầu học ngay 🚀]              │
└─────────────────────────────────────┘
```

---

### 8.2 Screen 2: Main Chat Interface

```
┌─────────────────────────────────────┐
│ ← Minh    🧠 42 facts    ⚙️ Settings│
│─────────────────────────────────────│
│                                     │
│  ┌─────────────────────────────┐    │
│  │ 🤖 Xin chào Minh! Hôm nay  │    │
│  │ bạn có 3 từ cần ôn lại.    │    │
│  │                             │    │
│  │ Tuần trước bạn hay nhầm    │    │
│  │ "affect" và "effect".       │    │
│  │ Thử dùng "effect" trong     │    │
│  │ câu sau nhé:                │    │
│  │                             │    │
│  │ "The new campaign had a     │    │
│  │ significant ___ on sales."  │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │ 👤 effect                   │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │ 🤖 ✅ Chính xác! "Effect"   │    │
│  │ là danh từ (kết quả).      │    │
│  │ "Affect" là động từ (ảnh   │    │
│  │ hưởng). Bạn đã nhớ rồi!   │    │
│  └─────────────────────────────┘    │
│                                     │
│─────────────────────────────────────│
│ 💬 Nhập tin nhắn...       [Gửi →]  │
│  [💡 Gợi ý]  [🏳️ Give up]          │
└─────────────────────────────────────┘
```

---

### 8.3 Screen 3: Progress Dashboard

```
┌─────────────────────────────────────┐
│ 📊 Tiến độ của Minh                 │
│─────────────────────────────────────│
│                                     │
│  Accuracy 30 ngày qua               │
│  ████████████████░░░░  78%          │
│  T4   T5   T6   T7   T8   T9  T10  │
│  60%  65%  70%  71%  75%  76% 78%  │
│                                     │
│─────────────────────────────────────│
│  🔴 Top lỗi sai cần chú ý          │
│                                     │
│  1. affect vs effect   ████░  18 lần│
│  2. present perfect    ███░░  12 lần│
│  3. a/an before vowel  ███░░   9 lần│
│  4. subject-verb agree ██░░░   7 lần│
│  5. preposition in/on  ██░░░   5 lần│
│                                     │
│─────────────────────────────────────│
│  📚 Từ vựng đã học: 124 từ         │
│  ✅ Đã thành thạo:   89 từ (72%)   │
│  🔄 Cần ôn thêm:    35 từ (28%)   │
│                                     │
│  [📅 Xem lịch ôn tập]              │
└─────────────────────────────────────┘
```

---

### 8.4 Screen 4: Spaced Repetition — "Bài ôn hôm nay"

```
┌─────────────────────────────────────┐
│ 🔄 Ôn tập hôm nay  (3/5 thẻ)       │
│─────────────────────────────────────│
│                                     │
│         ┌───────────────────┐       │
│         │                   │       │
│         │    NEGOTIATE      │       │
│         │                   │       │
│         │  [Lật thẻ để xem] │       │
│         └───────────────────┘       │
│                                     │
│  Đây là lần nhắc thứ 2              │
│  Lần cuối: 5 ngày trước             │
│                                     │
│  Bạn có nhớ nghĩa không?           │
│                                     │
│  [😅 Khó nhớ]  [🤔 Nhớ mờ]  [✅ Nhớ rõ]│
│                                     │
│  ← Bỏ qua hôm nay                  │
└─────────────────────────────────────┘
```

---

### 8.5 Screen 5: Mood Check-In (tính năng sáng tạo — xem mục 9)

```
┌─────────────────────────────────────┐
│ 🎯 Chào Minh, hôm nay thế nào?     │
│─────────────────────────────────────│
│                                     │
│  Trạng thái của bạn lúc này:        │
│                                     │
│  😴  😐  🙂  😊  🔥                │
│  Mệt  Bình  Ổn   Tốt  Tuyệt       │
│       thường                         │
│                                     │
│  ────────────────────────────────── │
│  💡 Hôm nay AI sẽ điều chỉnh        │
│     bài học phù hợp với bạn.        │
│                                     │
│  [Bỏ qua]    [Xác nhận →]          │
└─────────────────────────────────────┘
```

---

## 9. 💡 Tính Năng Sáng Tạo — Những Thứ Chưa Được Nói Đến

> Đây là phần mà các sản phẩm hiện tại **không ai đang làm**, nhưng người dùng thực tế **thực sự cần**. Mỗi tính năng đều có cơ sở nghiên cứu độc lập.

---

### 💡 Creative Feature 1: Mood-Adaptive Session (Phiên Học Thích Ứng Cảm Xúc)

**Tính năng:** Trước mỗi phiên học, hệ thống hỏi người dùng một câu đơn giản về trạng thái hiện tại (5 mức: mệt → tuyệt vời). AI điều chỉnh loại bài tập, độ khó và thời lượng tương ứng.

| Trạng thái | Chiến lược AI |
|---|---|
| 😴 Mệt / Năng lượng thấp | Chỉ ôn tập flashcard đã biết, không học mới, session 5–7 phút |
| 🙂 Bình thường | Ôn + học mới 50/50, session 15–20 phút |
| 🔥 Năng lượng cao | Tăng độ khó, bài tập sản xuất (writing/speaking), session 25–30 phút |

**Vì sao quan trọng?**

Nghiên cứu từ Springer Nature (2023) trên nền tảng học ngoại ngữ di động Busuu cho thấy có mối liên hệ mạnh mẽ giữa cảm xúc tích cực và sự kiên trì trong học tập ngoại ngữ tự định hướng — cảm xúc như niềm vui, hy vọng và hứng thú gắn liền với việc ghi nhớ từ vựng. Ngược lại, nghiên cứu từ Cambridge Core (2024) chỉ ra rằng cảm xúc tiêu cực có tác động thu hẹp, thường cản trở tiến độ học ngôn ngữ thông qua ảnh hưởng đến các quá trình xử lý thông tin nhận thức.

**Insight thực tế:** Người dùng mở app lúc 11h đêm sau ngày làm việc căng thẳng và người mở app lúc 8h sáng đầu óc tỉnh táo — cần hai trải nghiệm học hoàn toàn khác nhau. Không có app nào đang làm điều này.

**Implementation:** Mood check-in < 5 giây (1 click), không bắt buộc. Dữ liệu mood được lưu vào Mem0 như một fact (`mood_pattern`), AI dần học được rhythm cảm xúc của từng người dùng.

---

### 💡 Creative Feature 2: Context Injection — "Học từ công việc của chính mình"

**Tính năng:** Người dùng paste trực tiếp một đoạn văn bản thực tế từ công việc (email tiếng Anh nhận được, đoạn tài liệu kỹ thuật, slide pitch...). AI phân tích và tạo bài học cá nhân hóa từ đúng ngữ liệu đó.

**Ví dụ flow:**
```
User: [paste] "Please ensure the deliverables are aligned 
with the stakeholder requirements before EOD."

AI: "Tôi thấy 3 từ khó trong đoạn này của bạn. 
     Hãy thử giải thích 'deliverables' theo cách bạn hiểu?"

→ Bài học được tạo từ chính email boss gửi hôm nay.
```

**Vì sao quan trọng?**

Đây là cách giải quyết triệt để "Bệnh Nghẽn" (🔴) — không có bài tập generic nào sánh được với việc học từ vựng mà người dùng SẼ dùng ngày mai. Nguyên lý này có nền tảng trong lý thuyết **Situated Learning** (Lave & Wenger, 1991): kiến thức được học trong ngữ cảnh thực tế thì khả năng transfer sang ứng dụng thực tế cao hơn đáng kể so với học decontextualized.

**Implementation:** Text input box trong chat UI. LangGraph xử lý văn bản qua một node phân tích riêng (`context_analyzer`), extract từ vựng khó, tạo mini-lesson và lưu vào Mem0 dưới dạng `industry_vocab` fact.

---

### 💡 Creative Feature 3: Error DNA Fingerprint — Bản Đồ Lỗi Cá Nhân

**Tính năng:** Thay vì chỉ list "top 5 lỗi sai", hệ thống xây dựng một **"Error DNA"** — biểu đồ radar trực quan thể hiện profile lỗi của người dùng theo 6 chiều ngôn ngữ.

```
         Grammar
            ▲
            │ ████
   Writing ◄┼────►  Vocabulary
            │  ██
            ▼
         Preposition
         
  Pronunciation    Collocations
```

Mỗi chiều hiển thị: điểm yếu hiện tại, xu hướng cải thiện, và so sánh với người dùng cùng trình độ (anonymized).

**Vì sao quan trọng?**

Các ứng dụng hiện tại chỉ show raw error count — không trả lời được câu hỏi "Tôi yếu ở đâu *nhất* và nên ưu tiên học gì?" Error DNA biến dữ liệu thô thành insight hành động được, tạo ra một **vòng lặp động lực**: nhìn thấy điểm yếu rõ ràng → có mục tiêu cụ thể → học → thấy radar chart thay đổi → motivated tiếp tục.

Nghiên cứu PMC (2024) về cảm xúc trong lớp học ngôn ngữ xác nhận rằng cảm xúc hướng dẫn quá trình chú ý của người học và việc sử dụng nguồn lực nhận thức, kích thích và duy trì hứng thú học, đồng thời thúc đẩy hoặc cản trở sự tham gia và tự điều chỉnh trong quá trình học. Một visualization rõ ràng về tiến độ tạo ra feedback loop cảm xúc tích cực giúp duy trì engagement.

**Implementation:** Radar chart component trên Dashboard. Dữ liệu từ Mem0 `error_pattern` facts, được aggregate theo 6 category và cập nhật sau mỗi phiên.

---

### 💡 Creative Feature 4: Retrieval-First Morning Brief

**Tính năng:** Mỗi sáng (hoặc khi mở app lần đầu trong ngày), thay vì bắt đầu bài mới, hệ thống gửi **"Morning Brief"** — 3 câu hỏi retrieval nhanh về kiến thức đã học, trước khi bắt đầu nội dung mới.

```
☀️ Chào buổi sáng, Minh!

Trước khi học hôm nay, thử nhớ lại:
Q1: "Negotiate" nghĩa là gì? (học 3 ngày trước)
Q2: Phân biệt "its" và "it's"? (học tuần trước)  
Q3: Dùng Present Perfect khi nào? (lỗi tuần 2)

[Trả lời] → Bắt đầu bài học hôm nay
```

**Vì sao quan trọng?**

Đây là ứng dụng của **Retrieval Practice Effect** — một trong những hiệu ứng học tập được nghiên cứu nhiều nhất trong khoa học thần kinh nhận thức. Retrieval practice là chiến lược học hiệu quả cho việc học từ vựng ngoại ngữ. Nhiều nghiên cứu trước đây đã chỉ ra rằng retrieval practice thúc đẩy học ngoại ngữ tốt hơn so với việc học lại nhiều lần.

Quan trọng hơn, cả hai nhóm feedback tức thì và feedback trì hoãn đều vượt trội so với nhóm không có feedback và nhóm học lại (restudying) trong bài kiểm tra trì hoãn một tháng. Morning Brief tích hợp cả retrieval lẫn feedback tức thì — double win.

Chỉ 3 câu hỏi, mất < 2 phút, nhưng có thể là tính năng tạo ra impact lớn nhất về retention.

**Implementation:** Scheduled trigger khi user mở app buổi sáng đầu tiên. Questions được chọn từ Mem0 bằng thuật toán SM-2 (đúng thời điểm cần ôn). Không thể skip — nhưng có thể "remind me later" để hoãn sang buổi trưa.

---

## 10. Kiến Trúc Kỹ Thuật

### 10.1 Stack công nghệ

| Tầng | Công nghệ | Vai trò |
|---|---|---|
| **LLM Core** | OpenAI GPT-4o / Claude Sonnet | NLP, hiểu ngữ cảnh, tạo phản hồi |
| **Memory Layer** | Mem0 (Vector DB + Entity Extraction) | Lưu & truy xuất facts, nén lịch sử hội thoại |
| **Orchestration** | LangGraph | Điều phối 4-node pipeline, quản lý state |
| **Backend API** | FastAPI (Python) | REST API, webhook, session management |
| **Database** | PostgreSQL + Redis | User profile, logs; Redis cho cache & rate limit |
| **Frontend** | Next.js + TailwindCSS | Web app mobile-responsive, SSR |
| **Infrastructure** | Vercel (FE) + Railway/AWS (BE) | Deploy nhanh, scale linh hoạt |
| **Monitoring** | Datadog / Sentry | APM, error tracking, token cost monitoring |

### 10.2 Luồng dữ liệu (Data Flow)

```
User Input
    ↓
[Backend API] — Auth, rate limit check
    ↓
[Memory Retrieval] — Mem0 semantic search, top-K=10 facts
    ↓
[Context Builder] — facts + 3–5 turns history + system prompt
    ↓
[Scaffolding Engine] — LLM detect error → hints → response
    ↓
[Memory Writer] — extract new facts → upsert Mem0
    ↓
User sees Response
```

### 10.3 Mem0 Fact Schema

```json
{
  "user_id": "uuid",
  "fact_type": "error_pattern | vocabulary | mood_pattern | industry_vocab | skill_level | topic_preference",
  "content": "User confuses 'affect' (verb) with 'effect' (noun)",
  "embedding": [...],
  "importance_score": 0.85,
  "last_updated": "2025-04-10",
  "review_count": 3,
  "source_session": "session_id"
}
```

---

## 11. Non-Functional Requirements

| Danh mục | Yêu cầu | Chỉ số đo lường |
|---|---|---|
| **Performance** | Response time < 3s end-to-end | P95 < 3s; P99 < 5s |
| **Memory Retrieval** | Truy xuất Mem0 < 1 giây | P95 < 1s (Datadog APM) |
| **Scalability** | 100–200 concurrent users | Load test không degradation |
| **Security** | Mã hóa at-rest và in-transit | AES-256; TLS 1.3 |
| **Privacy** | Xóa toàn bộ memory theo yêu cầu | Hoàn thành < 30 giây |
| **Availability** | Uptime 99.5% giờ cao điểm | SLA 99.5%/tháng |
| **Accessibility** | Mobile-responsive, WCAG AA | Lighthouse ≥ 85 |
| **Token Cost** | Giảm 90% vs full-history injection | Cost tracking per user/session |

---

## 12. Phân Tích Đối Thủ & Định Vị

| Sản phẩm | Giá | Ưu điểm | Nhược điểm |
|---|---|---|---|
| **Duolingo Max** | ~$30/tháng | Gamification, streak, giải thích lỗi cơ bản | Trí nhớ cục bộ; AI vài ngôn ngữ; không scaffolding thực sự |
| **ChatGPT / Gemini** | Free–$20/tháng | NLP vượt trội, linh hoạt | Không sư phạm; bao che lỗi; không lưu profile lỗi vĩnh viễn; context drift 39% |
| **Agentic Tutor** | TBD (freemium) | Persistent Memory xuyên phiên; Scaffolding sư phạm; Mood-Adaptive; Context Injection | Chưa gamification; mới alpha; cần build trust privacy |

> 💡 **USP:** Agentic Tutor không chỉ là chatbot — đây là gia sư biết rõ "bạn là ai" từ 3 tháng trước, điều chỉnh theo cảm xúc hôm nay, và học từ chính email công việc của bạn. Tăng **26% accuracy** cá nhân hóa, giảm **90% chi phí token**.

---

## 13. Roadmap Alpha — 6 Tuần

| Sprint | Tuần | Deliverables | Definition of Done |
|---|---|---|---|
| **Sprint 1** | 1–2 | Setup infra; OpenAI + Mem0 tích hợp; Onboarding flow; DB schema; Admin dashboard token cost | API trả lời được, Mem0 lưu fact đầu tiên, admin xem được chi phí |
| **Sprint 2** | 3–4 | LangGraph 4-node; Scaffolding Engine; SM-2 Spaced Repetition; Chat UI; Mood check-in | End-to-end chat → memory → scaffold → response < 3s |
| **Sprint 3** | 5–6 | Progress Dashboard; Memory compression; Context Injection MVP; Alpha 100 users; Bug fix | 100 users active; D7 retention ≥ 35%; zero P0 bugs |

**Sau alpha (Tuần 7+):** Phân tích dữ liệu, tinh chỉnh thuật toán, Error DNA visualization, Morning Brief, chuẩn bị open beta.

---

## 14. Metrics & KPIs

### 14.1 KPIs người dùng

| KPI | Baseline (ngành) | Target Alpha | Target Beta |
|---|---|---|---|
| D7 Retention | ~20% | ≥ 35% | ≥ 40% |
| D30 Retention | ~15% | ≥ 20% | ≥ 25% |
| Sessions/User/Week | 2–3 | ≥ 4 | ≥ 5 |
| Avg Session Duration | < 10 phút | 15–20 phút | 18–23 phút |
| NPS Score | N/A | ≥ 30 | ≥ 45 |
| Mood Check-in Rate | N/A | ≥ 60% | ≥ 70% |

### 14.2 KPIs kỹ thuật

- Memory retrieval latency P95 **< 1 giây**
- End-to-end response P95 **< 3 giây**
- Token cost/session giảm **≥ 80%** (target 90%)
- Personalization accuracy **+26%** vs non-memory baseline
- System uptime **≥ 99.5%/tháng**

---

## 15. Rủi Ro & Giảm Thiểu

| # | Rủi ro | Xác suất | Tác động | Giảm thiểu | Chủ sở hữu |
|---|---|---|---|---|---|
| R1 | Mem0 latency > 1s | 🟡 Trung bình | 🔴 Cao | Cache repeated queries; fallback simplified memory nếu > 2s | Tech Lead |
| R2 | OpenAI cost vượt budget | 🔴 Cao | 🔴 Cao | Rate limit 50 queries/user/ngày; daily cost monitor; switch Claude | PM + Tech Lead |
| R3 | Alpha users không active đủ | 🟡 Trung bình | 🟡 Trung bình | Premium free 3 tháng; daily push; weekly check-in call | PM + Marketing |
| R4 | Scaffolding cho đáp án quá sớm/muộn | 🟡 Trung bình | 🟡 Trung bình | A/B test 2 chiến lược; feedback form sau mỗi session | AI/ML Engineer |
| R5 | Privacy: memory lưu dữ liệu nhạy cảm | 🟢 Thấp | 🔴 Rất cao | PII scrubbing trước Mem0; user review + delete bất kỳ lúc nào | Security Engineer |
| R6 | Mood data bị dùng sai mục đích | 🟢 Thấp | 🔴 Cao | Mood data chỉ dùng cho session adaptation, không share, không dùng cho quảng cáo | PM + Legal |

---

## 16. Phụ Lục

### 16.1 Thuật ngữ

| Thuật ngữ | Định nghĩa |
|---|---|
| **Mem0** | Thư viện quản lý bộ nhớ dài hạn cho AI, dùng vector DB để lưu và truy xuất facts cá nhân hóa. |
| **LangGraph** | Framework stateful, multi-actor AI applications dưới dạng đồ thị có hướng (DAG). |
| **Scaffolding** | Phương pháp sư phạm: AI hỗ trợ từng bước nhỏ, gợi ý thay vì cho đáp án thẳng. |
| **Context Drift** | Hiện tượng AI giảm chất lượng phản hồi khi hội thoại kéo dài, thiếu memory cấu trúc. |
| **SM-2** | Thuật toán Spaced Repetition của SuperMemo, tối ưu lịch ôn dựa trên hiệu suất người học. |
| **Retrieval Practice Effect** | Hiệu ứng tâm lý học nhận thức: chủ động gợi nhớ thông tin giúp retention tốt hơn đọc lại nhiều lần. |
| **Error DNA** | Biểu đồ radar trực quan hóa profile lỗi sai cá nhân theo 6 chiều ngôn ngữ. |
| **Context Injection** | Tính năng cho phép paste văn bản thực tế từ công việc để AI tạo bài học từ đó. |
| **Mood-Adaptive Session** | Tính năng điều chỉnh độ khó và loại bài tập dựa trên trạng thái cảm xúc đầu phiên. |

### 16.2 Tài liệu tham khảo

**Từ Problem Brief (nguồn gốc):**
- Language Learning Market Size, Share & Trends Analysis, 2035
- Mem0 AI Memory Research: 26% Accuracy Boost for LLMs
- LLMs Get Lost In Multi-Turn Conversation — accuracy degrades 39%
- Tutorbase — Language Learning Statistics 2026: 35+ Key ESL Facts
- Teaching According to Students' Aptitude: Personalized Mathematics Tutoring via Persona-, Memory-, and Forgetting-Aware LLMs

**Bổ sung cho phần sáng tạo (dẫn chứng mới):**
- Pekrun, R. et al. (2024). *The role of positive and negative emotions in foreign language learning: A research agenda.* Language Teaching, Cambridge Core. — Cơ sở cho Mood-Adaptive Session.
- Lave, J. & Wenger, E. (1991). *Situated Learning: Legitimate Peripheral Participation.* Cambridge University Press. — Cơ sở cho Context Injection.
- Hudilainen & Klepikova (2016). *The effectiveness of computer-based spaced repetition in foreign language vocabulary instruction.* CALICO Journal, Vol. 33(3). — Nghiên cứu chứng minh rằng chỉ cần trung bình ba phút mỗi ngày với các hoạt động từ vựng được tạo tự động, học viên EFL đã tăng tỷ lệ ghi nhớ từ vựng dài hạn lên gấp ba lần.
- Li et al. (2022). *Retrieval practice enhances learning and memory retention of French words in Chinese-English bilinguals.* ScienceDirect. — Cơ sở cho Retrieval-First Morning Brief.
- Springer Nature (2023). *Motivational and emotional states in self-directed language learning: a longitudinal study.* — Cơ sở cho Mood-Adaptive Session.

---

*Tài liệu này được soạn thảo cho mục đích nội bộ của Agentic Tutor Team. Phiên bản 2.0 — Tháng 4, 2025.*
*Nội dung bắt buộc có nguồn gốc từ Problem Brief gốc. Các phần sáng tạo (mục 9) có dẫn chứng nghiên cứu độc lập.*