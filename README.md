# A20-App-134

## Tài liệu nộp build bao gồm:
- `docs/compact submission/evaluation/report.md`: báo cáo kết quả đánh giá khả năng nhận diện lỗi từ câu chat của người dùng.
- `docs/compact submission/evaluation/gold_delta.jsonl`: Bộ câu hỏi kiểm thử được nhắc đến trong report.
- feedback từ người dùng: file `docs/compact submission/evaluation/Customer_Feedback.csv` lấy từ người dùng khi điền form và feedback từ discord channel có tên LingoAI - Gia sư Tiếng Anh nhớ mọi thứ bạn nói (link discord: https://discord.com/channels/1486186709476577381/1504840027467681832)
- ảnh chụp màn hình `docs/compact submission/evaluation/feedback_example.png`: 1 feedback ví dụ từ người dùng trong dicord channel
- `docs/compact submission/archiecture.png`: sơ đồ kiến trúc hệ thống.

## 1. Tên dự án

**A20-App-134 - Agentic Language Tutor**

Gia sư tiếng Anh cá nhân hóa cho người học Việt Nam, giúp người học luyện giao tiếp, sửa lỗi, ôn tập đúng thời điểm và theo dõi tiến bộ theo cách dễ hiểu.

## 2. Mô tả ngắn gọn

A20-App-134 giúp người học tiếng Anh có một “người hướng dẫn” luôn sẵn sàng: có thể hỏi đáp, luyện câu, nhận gợi ý khi bí, xem lại lỗi sai thường gặp và ôn tập theo lịch cá nhân. Thay vì học rời rạc, người học có một lộ trình được điều chỉnh theo trình độ, mục tiêu và ngành nghề của mình.

Sản phẩm phù hợp với người học muốn cải thiện tiếng Anh thực dụng, đặc biệt là tiếng Anh học thuật, công việc, giao tiếp hằng ngày và các ngữ cảnh chuyên môn như marketing, tài chính, công nghệ, giáo dục hoặc chăm sóc sức khỏe.

## 3. Mục tiêu / vấn đề giải quyết

- Giúp người học biết nên học gì tiếp theo thay vì tự đoán hoặc học lan man.
- Giúp phát hiện lỗi sai lặp lại, ví dụ lỗi dùng từ, ngữ pháp, diễn đạt hoặc sắc thái trong câu.
- Đưa ra gợi ý từng bước để người học tự sửa trước khi xem đáp án hoàn chỉnh.
- Nhắc ôn tập đúng lúc để kiến thức không bị quên sau vài ngày.
- Cho người học thấy tiến bộ của mình qua dashboard, Error DNA và lịch sử luyện tập.
- Tôn trọng quyền riêng tư: người học có thể quản lý hoặc xóa dữ liệu cá nhân.

## 4. Tính năng chính

- **Hồ sơ học tập cá nhân:** người học khai báo trình độ, mục tiêu và ngành nghề để hệ thống gợi ý nội dung phù hợp.
- **Gia sư AI qua chat:** hỏi đáp, luyện viết câu, sửa lỗi và nhận phản hồi bằng ngôn ngữ dễ hiểu.
- **Gợi ý khi gặp khó:** thay vì đưa đáp án ngay, hệ thống có thể gợi ý từng bước để người học tự suy nghĩ.
- **Bài học theo lộ trình:** tiếp tục bài học hiện tại, làm câu hỏi luyện tập, xem flashcards và hoàn thành lesson.
- **Ôn tập thông minh:** hệ thống đưa lại từ vựng hoặc lỗi sai vào đúng thời điểm cần ôn.
- **Error DNA:** hiển thị những kiểu lỗi người học hay mắc để biết mình cần cải thiện điểm nào.
- **Morning Brief:** bài luyện ngắn mỗi ngày, phù hợp để duy trì thói quen học đều.
- **Dashboard tiến độ:** xem số liệu học tập, từ vựng đã học, lỗi thường gặp và mức độ cải thiện.
- **Quản lý tài khoản:** đăng ký, đăng nhập, đặt lại mật khẩu và đăng nhập bằng Google.
- **Quyền riêng tư dữ liệu:** người học có thể yêu cầu xóa dữ liệu cá nhân trong phần cài đặt.
- **Trang quản trị:** hỗ trợ đội vận hành theo dõi người dùng, chỉ số hệ thống và xuất dữ liệu cần thiết.

## 5. Công nghệ sử dụng

| Thành phần | Công nghệ |
|---|---|
| Backend | FastAPI, Python 3.11+, Pydantic v2 |
| Database | PostgreSQL 16, SQLAlchemy 2, Alembic |
| Cache / session | Redis 7 |
| Vector memory | Mem0, Qdrant 1.11 |
| LLM providers | Gemini, Groq, OpenAI, Anthropic fallback hooks |
| Orchestration | LangGraph, APScheduler |
| Frontend | Vite, React 18, React Router, Zustand, React Query |
| UI / charts | TailwindCSS, Recharts |
| Evaluation | Python evaluation runner, JSONL/CSV artifacts |
| DevOps | Docker Compose, Railway backend config, Vercel frontend config |
| Observability | Sentry optional, local LLM call logs |

## 6. Hướng dẫn cài đặt

### Yêu cầu môi trường

- Docker Desktop hoặc Docker Engine + Docker Compose 2.x
- Git
- Python 3.11+ nếu chạy backend/data pipeline ngoài Docker
- Node.js 18+ nếu chạy frontend ngoài Docker

### Cài đặt lần đầu

```bash
git clone <repository-url>
cd A20-App-134
```

Tạo file môi trường cho Docker Compose:

```bash
cd src
cp .env.example .env
```

Cập nhật các biến trong `src/.env` nếu cần dùng LLM, OAuth, email hoặc Sentry:

```env
GEMINI_API_KEY=
GROQ_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
RESEND_API_KEY=
SENTRY_DSN=
```

Nếu cần tạo Pull Request, chạy hook logging một lần trước khi push:

```bash
bash scripts/setup_hooks.sh
```

## 7. Hướng dẫn chạy dự án

### Chạy bằng Docker Compose

Từ thư mục `src`:

```bash
docker compose up -d --build
```

Các dịch vụ chính:

| Dịch vụ | Địa chỉ |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Readiness check | http://localhost:8000/ready |
| Qdrant | http://localhost:6333 |
| pgAdmin | http://localhost:5050 |

Khởi tạo database và seed dữ liệu sau khi container đã healthy:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seeders.seed_processed
```

Kiểm tra nhanh backend:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### Chạy test backend

```bash
cd src
docker compose exec backend pytest -v
```

Chạy một nhóm test cụ thể:

```bash
docker compose exec backend pytest tests/test_sm2_scheduler.py -v
docker compose exec backend pytest tests/test_learning_phase3_api.py -v
docker compose exec backend pytest tests/test_eval_error_spans_chat.py -v
```

### Chạy frontend ngoài Docker

```bash
cd src/frontend
npm install
npm run dev
```

Build production:

```bash
npm run build
```

### Chạy data pipeline

Từ thư mục gốc repo:

```bash
pip install -e .
python -m data_pipeline process-existing
python -m data_pipeline quality-process
python -m data_pipeline validate
python -m data_pipeline audit
```

### Chạy evaluation

Backend cần đang chạy tại `http://localhost:8000`.

```powershell
$env:PYTHONPATH='src;src\backend'
python -m evaluations.runner --suite english_error_span_delta --gold-delta data\evaluation\error_eval\gold_delta.jsonl --sample-size 100 --backend http://localhost:8000 --requests-per-user 45
```

Kết quả máy đọc được ghi vào `data/evaluation/runs/<run_id>`, báo cáo Markdown ghi vào `docs/evaluation/runs/<run_id>/report.md`.

## 8. Hướng dẫn sử dụng sản phẩm

1. Mở frontend tại http://localhost:5173.
2. Đăng ký tài khoản mới hoặc đăng nhập bằng tài khoản có sẵn.
3. Hoàn thành onboarding để hệ thống hiểu trình độ, mục tiêu học và ngữ cảnh sử dụng tiếng Anh của bạn.
4. Vào **Chat** khi muốn hỏi bài, luyện viết câu, sửa lỗi hoặc nhờ giải thích một cách diễn đạt.
5. Vào **Review** để ôn lại các flashcards đến hạn, đặc biệt là những từ hoặc lỗi bạn dễ quên.
6. Vào **Dashboard** để xem tiến độ, Error DNA và các điểm cần cải thiện tiếp theo.
7. Vào **Settings** để cập nhật tùy chọn cá nhân hoặc xóa dữ liệu khi cần.
8. Nếu là admin, sử dụng admin dashboard để theo dõi tình trạng vận hành và hỗ trợ người dùng.

## Cấu trúc thư mục chính

```text
.
├── src/
│   ├── docker-compose.yml
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/v1/          # auth, chat, learning, review, analytics, admin, GDPR
│   │   │   ├── core/            # config, database, Redis, Mem0, middleware
│   │   │   ├── models/          # SQLAlchemy và Pydantic models
│   │   │   ├── services/        # LLM, LangGraph, SM-2, Error DNA, scheduler
│   │   │   └── seeders/         # seed processed data vào database
│   │   ├── alembic/             # database migrations
│   │   └── tests/               # backend test suite
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── pages/           # Home, Auth, Chat, Review, Dashboard, Settings, Admin
│   │   │   ├── components/      # chat, learning, review, dashboard, common
│   │   │   ├── services/        # API clients
│   │   │   └── stores/          # Zustand stores
│   │   └── package.json
│   ├── data_pipeline/           # data collection, processing, validation
│   └── evaluations/             # evaluation runner và suites
├── data/
│   ├── processed/               # curated runtime data
│   ├── curriculum_skeleton/     # lesson curriculum A2-C2
│   └── evaluation/              # gold labels và run artifacts
├── docs/                        # architecture, deployment, evaluation, requirements
├── AGENTS.md                    # quy tắc làm việc với AI coding agents
├── JOURNAL.md
└── WORKLOG.md
```

## Ghi chú đóng góp

- Không commit `.ai-log/*.jsonl`.
- PR description cần có đúng format:

```markdown
## Summary
<description of changes>

## Changes
- <list of changed files>
```

- Tài liệu song hành quan trọng:
  - `AGENTS.md`: quy tắc repo và PR.
  - `docs/SPRINT.md`: sprint tracker.
  - `docs/system architecture/architecture_target.md`: kiến trúc mục tiêu.
  - `docs/system architecture/requirements.md`: yêu cầu hệ thống.
