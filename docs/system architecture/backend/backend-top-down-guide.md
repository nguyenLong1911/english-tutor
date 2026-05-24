# Hướng Dẫn Hiểu Backend Theo Kiểu Top-Down

Tài liệu này giúp bạn hiểu backend bằng cách đi từ ngoài vào trong:

```text
1. Backend gồm những thư mục/file lớn nào?
2. Mỗi thư mục dùng để làm gì?
3. Trong từng thư mục có những file quan trọng nào?
4. Nên đọc file nào trước?
5. Sau khi hiểu cấu trúc, nên đi vào luồng code nào?
```

Cách đọc này phù hợp khi bạn chưa muốn nhảy ngay vào từng hàm chi tiết, mà muốn có bản đồ tổng quan trong đầu trước.

## 1. Vị Trí Backend Trong Dự Án

Backend nằm ở:

```text
src/backend/
```

Nhìn từ ngoài, thư mục này là phần server của app. Frontend gọi API tới backend, backend xử lý logic, gọi database/Redis/LLM, rồi trả JSON về frontend.

## 2. Cấu Trúc Cấp Cao Của `src/backend/`

Trong `src/backend/`, các phần quan trọng gồm:

```text
src/backend/
  app/
  alembic/
  tests/
  requirements.txt
  pytest.ini
  alembic.ini
  Dockerfile
  Dockerfile.railway
  start.sh
  README.md
```

Ý nghĩa từng phần:

| File/thư mục | Vai trò |
|---|---|
| `app/` | Code runtime chính của backend. Đây là nơi bạn sẽ đọc nhiều nhất. |
| `alembic/` | Database migrations: lịch sử thay đổi schema database. |
| `tests/` | Test backend. Dùng để kiểm tra API, service, auth, learning, memory, v.v. |
| `requirements.txt` | Danh sách thư viện Python backend cần cài. |
| `pytest.ini` | Cấu hình pytest cho test backend. |
| `alembic.ini` | Cấu hình Alembic migration. |
| `Dockerfile` | Cách build backend container thông thường. |
| `Dockerfile.railway` | Cách build backend cho Railway/deploy. |
| `start.sh` | Script chạy khi backend container start. |
| `README.md` | Ghi chú nhanh về backend, cách chạy, endpoint chính. |

Nếu bạn mới đọc backend, thứ tự nên xem là:

```text
1. README.md
2. start.sh
3. app/
4. alembic/
5. tests/
```

Không cần đọc `Dockerfile` ngay nếu mục tiêu là hiểu code nghiệp vụ.

## 3. `start.sh`: Backend Bắt Đầu Chạy Như Thế Nào?

File:

```text
src/backend/start.sh
```

File này cho biết container backend làm gì khi khởi động.

Luồng hiện tại:

```text
1. Chạy database migrations
2. Seed admin account nếu có cấu hình
3. Seed một số processed data
4. Start uvicorn server
```

Nội dung quan trọng:

```sh
alembic upgrade head
python -m app.seeders.seed_admin
python -m app.seeders.seed_processed --only vocabulary,error_bank,pedagogical_prompt,ielts_writing_sample
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
```

Giải thích:

- `alembic upgrade head`: cập nhật schema database lên version mới nhất.
- `seed_admin`: tạo admin user nếu có env `ADMIN_EMAIL` và `ADMIN_PASSWORD`.
- `seed_processed`: nạp dữ liệu mẫu/evaluation/demo vào DB.
- `uvicorn app.main:app`: chạy FastAPI app từ file `app/main.py`.

Điểm cần nhớ:

```text
Khi server thật sự chạy, entry point Python là app/main.py.
```

## 4. Thư Mục `app/`: Phần Quan Trọng Nhất

Thư mục:

```text
src/backend/app/
```

Cấu trúc chính:

```text
app/
  main.py
  mcp_client.py
  api/
  core/
  models/
  services/
  seeders/
  utils/
```

Ý nghĩa từng phần:

| File/thư mục | Vai trò |
|---|---|
| `main.py` | Cổng vào của backend FastAPI. Gắn middleware, exception handler, router. |
| `mcp_client.py` | Tích hợp MCP tools. Không phải luồng chính nếu bạn đang học API backend. |
| `api/` | Khai báo endpoint HTTP. Frontend gọi vào đây. |
| `core/` | Hạ tầng dùng chung: config, database, auth, Redis, middleware, memory client. |
| `models/` | Mô tả dữ liệu: database tables và request/response schemas. |
| `services/` | Logic nghiệp vụ chính. API thường gọi service. |
| `seeders/` | Script nạp dữ liệu mẫu/demo/evaluation. |
| `utils/` | Hàm tiện ích, ví dụ LLM client và validators. |

Cách nhớ nhanh:

```text
main.py  = app bắt đầu ở đâu
api/     = URL nằm ở đâu
core/    = hạ tầng dùng chung nằm ở đâu
models/  = dữ liệu có hình dạng gì
services/= nghiệp vụ thật nằm ở đâu
seeders/ = dữ liệu mẫu được nạp thế nào
utils/   = helper nhỏ
```

## 5. `app/main.py`: Cổng Vào Của Backend

File:

```text
src/backend/app/main.py
```

Vai trò:

```text
Tạo FastAPI app, cấu hình startup/shutdown, middleware, error handler, route health, và gắn các router API.
```

Bạn đọc file này để trả lời các câu hỏi:

- Backend app được tạo ở đâu?
- Khi app start thì chạy gì?
- Middleware nào chạy trước route?
- Các API trong `api/v1` được gắn vào app ở đâu?
- Prefix `/api/v1` đến từ đâu?

Các đoạn quan trọng:

```python
app = FastAPI(...)
```

Tạo app.

```python
@app.middleware("http")
async def request_trace_middleware(...)
```

Middleware log request, gắn trace id.

```python
app.add_middleware(RateLimitMiddleware, redis=get_redis())
```

Gắn rate limit middleware.

```python
app.add_middleware(CORSMiddleware, ...)
```

Cho frontend gọi backend và gửi cookie.

```python
app.include_router(chat.router, prefix="/api/v1")
```

Gắn router chat vào app.

Nên đọc `main.py` trước khi đọc các file API, vì nó cho bạn biết URL cuối cùng được tạo như thế nào.

## 6. Thư Mục `api/`: Nơi Khai Báo Endpoint

Thư mục:

```text
src/backend/app/api/
```

Bên trong chủ yếu là:

```text
api/
  v1/
```

Trong `api/v1/` có nhiều file:

```text
api/v1/
  auth.py
  auth_google.py
  onboarding.py
  chat.py
  learning.py
  review.py
  vocabulary.py
  analytics.py
  admin.py
  user.py
  mood.py
  context.py
  brief.py
  dna.py
  gdpr.py
```

Ý nghĩa từng file:

| File | Nhóm API |
|---|---|
| `auth.py` | Đăng ký, đăng nhập, đăng xuất, lấy user hiện tại, forgot/reset password. |
| `auth_google.py` | Đăng nhập Google OAuth. |
| `onboarding.py` | Tạo user/profile qua onboarding. |
| `chat.py` | API chat chính với tutor. |
| `learning.py` | Bài học, câu hỏi, flashcard, hoàn thành lesson. |
| `review.py` | Ôn tập SM-2 cho vocabulary/error flashcard. |
| `vocabulary.py` | Lấy từ vựng mới cho user. |
| `analytics.py` | Tổng hợp tiến độ, accuracy, vocabulary stats. |
| `admin.py` | Dashboard/admin metrics/users/cost/memory. |
| `user.py` | Lấy/xóa/cập nhật preference user. |
| `mood.py` | Mood check-in. |
| `context.py` | Phân tích pasted context. |
| `brief.py` | Morning brief. |
| `dna.py` | Error DNA. |
| `gdpr.py` | Delete data/audit GDPR. |

Cách đọc thư mục `api/v1`:

```text
Mỗi file thường tương ứng một nhóm màn hình hoặc nhóm chức năng frontend.
```

Ví dụ:

- Frontend login/register -> đọc `auth.py`.
- Frontend chat -> đọc `chat.py`.
- Frontend learning tab -> đọc `learning.py`.
- Frontend review tab -> đọc `review.py`.
- Frontend dashboard -> đọc `analytics.py`, `dna.py`.

## 7. Thư Mục `core/`: Hạ Tầng Dùng Chung

Thư mục:

```text
src/backend/app/core/
```

Các file quan trọng:

```text
core/
  config.py
  database.py
  redis_client.py
  security.py
  auth_dep.py
  middleware.py
  mem0_client.py
  observability.py
  llm_costs.py
```

Ý nghĩa:

| File | Vai trò |
|---|---|
| `config.py` | Đọc env/config bằng `Settings`. |
| `database.py` | Tạo SQLAlchemy engine/session và dependency `get_db`. |
| `redis_client.py` | Tạo Redis client và `SessionStore`. |
| `security.py` | Hash password, verify password, tạo/decode JWT. |
| `auth_dep.py` | Dependency lấy current user từ cookie JWT, check admin. |
| `middleware.py` | Rate limit middleware. |
| `mem0_client.py` | Kết nối memory layer Mem0/Qdrant hoặc fallback stub. |
| `observability.py` | Theo dõi lỗi/log/tracing. |
| `llm_costs.py` | Mapping/cấu hình tính chi phí LLM. |

Khi nào đọc `core/`?

- Muốn hiểu DB session đến từ đâu -> `database.py`.
- Muốn hiểu cookie/JWT -> `security.py`, `auth_dep.py`.
- Muốn hiểu Redis session -> `redis_client.py`.
- Muốn hiểu rate limit -> `middleware.py`.
- Muốn hiểu env config -> `config.py`.

Đây là thư mục “hạ tầng”. API và service gọi vào đây rất nhiều.

## 8. Thư Mục `models/`: Dữ Liệu Có Hình Dạng Gì?

Thư mục:

```text
src/backend/app/models/
```

Có hai loại file trong `models/`:

```text
1. ORM models: mô tả bảng database.
2. Pydantic schemas: mô tả request/response.
```

Các file đáng chú ý:

```text
models/
  schemas.py
  user.py
  vocabulary.py
  session_log.py
  mood.py
  lesson_progress.py
  personal_review.py
  error_dna.py
  error_bank.py
  pedagogical_prompt.py
  ielts_writing_sample.py
  memory_fact_outbox.py
  email_outbox.py
  delete_request.py
```

Ý nghĩa:

| File | Vai trò |
|---|---|
| `schemas.py` | Pydantic schemas: request/response như `ChatRequest`, `ChatResponse`, `UserOut`, `LearningState`. |
| `user.py` | Bảng `user_profile`. |
| `vocabulary.py` | Bảng `vocabulary` và `user_vocabulary`. |
| `session_log.py` | Log mỗi phiên/lượt chat, dùng cho analytics/cost/progress. |
| `mood.py` | Mood check-in logs. |
| `lesson_progress.py` | Trạng thái tiến độ bài học của user. |
| `personal_review.py` | Lỗi cá nhân, flashcard lỗi, review flashcard. |
| `error_dna.py` | Snapshot Error DNA. |
| `error_bank.py` | Bộ lỗi mẫu/curated, chủ yếu dùng seed/eval/demo. |
| `pedagogical_prompt.py` | Prompt sư phạm mẫu/seed. |
| `ielts_writing_sample.py` | IELTS sample seed/eval. |
| `memory_fact_outbox.py` | Queue ghi memory facts. |
| `email_outbox.py` | Queue email như reset password. |
| `delete_request.py` | Lưu request xóa dữ liệu/GDPR. |

Cách đọc `models/`:

```text
Nếu đang đọc một API và thấy payload: ChatRequest,
hãy mở schemas.py tìm ChatRequest.

Nếu đang đọc service và thấy db.get(User, ...),
hãy mở user.py xem User có field gì.
```

Lưu ý:

```text
Một số file import app.models.processed_dataset_schemas.
Trong cây thư mục hiện tại, file schema chính là app/models/schemas.py.
Nếu chạy app gặp lỗi import, cần kiểm tra alias/module này.
```

## 9. Thư Mục `services/`: Logic Nghiệp Vụ Chính

Thư mục:

```text
src/backend/app/services/
```

Đây là thư mục quan trọng thứ hai sau `api/`.

Nếu `api/` trả lời câu hỏi:

```text
URL nào gọi hàm nào?
```

Thì `services/` trả lời câu hỏi:

```text
Logic thật được xử lý thế nào?
```

Các file quan trọng:

```text
services/
  langgraph_orchestrator.py
  scaffolding_engine.py
  system_prompt.py
  guardrails.py
  personalization.py
  personal_error_context.py
  profile_memory_extractor.py
  error_capture_service.py
  sm2_scheduler.py
  scheduler.py
  lesson_catalog.py
  lesson_question_generator.py
  lesson_vocabulary_provider.py
  learner_profile_provider.py
  progress_analytics.py
  metrics_collector.py
  memory_outbox.py
  memory_compactor.py
  email_provider.py
  email_digest.py
  token_cost.py
```

Ý nghĩa theo nhóm:

### Nhóm Chat/AI

| File | Vai trò |
|---|---|
| `langgraph_orchestrator.py` | Điều phối pipeline chat nhiều node. |
| `scaffolding_engine.py` | Build prompt, gọi LLM, parse response/sửa lỗi. |
| `system_prompt.py` | Tạo system prompt/persona cho tutor. |
| `guardrails.py` | Chặn input/output nguy hiểm hoặc prompt injection. |
| `token_cost.py` | Ước tính token/cost cho chat log. |

### Nhóm Memory/Cá Nhân Hóa

| File | Vai trò |
|---|---|
| `personalization.py` | Làm giàu user profile bằng memory. |
| `profile_memory_extractor.py` | Rút facts từ tin nhắn user. |
| `personal_error_context.py` | Load lỗi cá nhân gần đây/đến hạn. |
| `memory_outbox.py` | Queue ghi memory facts. |
| `memory_compactor.py` | Nén/giới hạn memory facts. |

### Nhóm Lỗi Cá Nhân/Review

| File | Vai trò |
|---|---|
| `error_capture_service.py` | Lưu lỗi user mắc và tạo flashcard lỗi. |
| `error_dna_aggregator.py` | Tổng hợp Error DNA. |
| `error_taxonomy.py` | Phân loại lỗi. |
| `sm2_scheduler.py` | Tính lịch ôn tập SM-2. |

### Nhóm Learning

| File | Vai trò |
|---|---|
| `lesson_catalog.py` | Đọc danh sách/bài học từ curriculum skeleton. |
| `lesson_question_generator.py` | Tạo câu hỏi practice cho lesson. |
| `lesson_vocabulary_provider.py` | Lấy vocabulary cho lesson, có fallback mock/metadata. |
| `learner_profile_provider.py` | Lấy learner profile phục vụ lesson flow. |

### Nhóm Analytics/Scheduler/Email

| File | Vai trò |
|---|---|
| `progress_analytics.py` | Tạo summary tiến độ học. |
| `metrics_collector.py` | Ghi metrics định kỳ. |
| `scheduler.py` | Start/stop background scheduler. |
| `email_provider.py` | Gửi email qua provider. |
| `email_digest.py` | Tạo/gửi digest email. |

Cách đọc `services/`:

```text
Đừng đọc tất cả cùng lúc.
Hãy bắt đầu từ API đang quan tâm, xem API gọi service nào, rồi mở đúng service đó.
```

Ví dụ:

```text
api/v1/chat.py
  -> services/langgraph_orchestrator.py
  -> services/scaffolding_engine.py
  -> services/error_capture_service.py
```

## 10. Thư Mục `seeders/`: Dữ Liệu Mẫu Và Evaluation

Thư mục:

```text
src/backend/app/seeders/
```

Các file chính:

```text
seeders/
  seed_admin.py
  seed_processed.py
  ingest_corpus_to_qdrant.py
```

Ý nghĩa:

| File | Vai trò |
|---|---|
| `seed_admin.py` | Tạo/cập nhật admin user từ env. |
| `seed_processed.py` | Nạp processed data vào Postgres/Mem0: vocabulary, error bank, prompts, IELTS samples. |
| `ingest_corpus_to_qdrant.py` | Đưa corpus static vào Qdrant cho retrieval experiments/eval/demo. |

Theo bản mới của `docs/data layer/scraping/data_planning.md`, static seed data chủ yếu dùng cho:

- Demo.
- Evaluation.
- Benchmark.
- Regression test.
- Dữ liệu mẫu trước khi có user thật.

Không nên hiểu seed data là điều kiện bắt buộc để tutor biết dạy tiếng Anh. Runtime thật nên ưu tiên dữ liệu phát sinh từ user.

## 11. Thư Mục `utils/`: Helper Nhỏ

Thư mục:

```text
src/backend/app/utils/
```

Các file:

```text
utils/
  llm.py
  validators.py
```

Ý nghĩa:

| File | Vai trò |
|---|---|
| `llm.py` | Wrapper gọi LLM provider như Gemini/Groq/mock, tracking usage. |
| `validators.py` | Helper validate/scrub dữ liệu, ví dụ PII. |

Khi nào đọc `llm.py`?

```text
Khi bạn muốn hiểu get_llm_client() chọn provider nào,
Gemini/Groq/mock được gọi ra sao,
token usage được track thế nào.
```

## 12. Thư Mục `alembic/`: Database Migration

Thư mục:

```text
src/backend/alembic/
```

Cấu trúc:

```text
alembic/
  env.py
  script.py.mako
  versions/
```

Ý nghĩa:

| File/thư mục | Vai trò |
|---|---|
| `env.py` | Cấu hình Alembic chạy migration với app/database. |
| `script.py.mako` | Template tạo file migration mới. |
| `versions/` | Danh sách migration đã tạo. |

Bạn đọc `alembic/versions/` khi muốn biết:

- Bảng nào được tạo khi nào.
- Column nào được thêm sau.
- Schema database thay đổi theo lịch sử ra sao.

Ví dụ migration:

```text
0001_init_schema.py
0002_metrics_log.py
0003_add_password_hash.py
...
```

## 13. Thư Mục `tests/`: Test Backend

Thư mục:

```text
src/backend/tests/
```

Ý nghĩa:

```text
Các test giúp bạn hiểu expected behavior của backend.
```

Một số test đáng đọc:

| File test | Giúp hiểu gì? |
|---|---|
| `test_auth_security.py` | Auth, password, JWT, cookie. |
| `test_integration.py` | Luồng tích hợp chính. |
| `test_learning_phase1_services.py` | Service learning cơ bản. |
| `test_learning_phase2_question_generator.py` | Cách sinh câu hỏi lesson. |
| `test_learning_phase3_api.py` | API learning. |
| `test_learning_phase4_langgraph.py` | Learning flow trong LangGraph. |
| `test_sm2_scheduler.py` | Thuật toán SM-2. |
| `test_error_capture_service.py` | Lưu lỗi và tạo flashcard. |
| `test_error_dna_aggregator.py` | Tổng hợp Error DNA. |
| `test_config_urls.py` | Config URL. |

Khi chưa hiểu một service, đọc test của service đó đôi khi dễ hơn đọc implementation.

## 14. Bản Đồ Top-Down Của Backend

Đây là bản đồ nên ghi nhớ:

```text
src/backend/
  start.sh
    -> cho biết backend start bằng command nào

  app/
    main.py
      -> tạo app, middleware, router

    api/v1/
      -> khai báo endpoint HTTP

    core/
      -> config, database, auth, redis, middleware

    models/
      -> schema request/response và bảng database

    services/
      -> logic nghiệp vụ chính

    seeders/
      -> nạp dữ liệu mẫu/demo/eval

    utils/
      -> helper nhỏ như LLM client

  alembic/
    -> lịch sử schema database

  tests/
    -> expected behavior của hệ thống
```

## 15. Nên Đọc Theo Thứ Tự Nào?

Nếu bạn muốn hiểu backend từ trên xuống, hãy đọc theo các vòng.

### Vòng 1: Bản Đồ Cấp Cao

Đọc:

```text
src/backend/README.md
src/backend/start.sh
src/backend/app/main.py
```

Mục tiêu:

```text
Biết app start thế nào, entry point ở đâu, router được gắn ra sao.
```

### Vòng 2: Các Folder Chính Trong `app/`

Đọc tên file trước, chưa cần đọc chi tiết:

```text
app/api/v1/
app/core/
app/models/
app/services/
```

Mục tiêu:

```text
Nhìn tên file là đoán được chức năng nằm ở đâu.
```

### Vòng 3: Một Luồng API Đơn Giản

Nên chọn auth trước:

```text
api/v1/auth.py
core/security.py
core/auth_dep.py
models/user.py
```

Mục tiêu:

```text
Hiểu một API từ route -> DB -> response.
```

### Vòng 4: Luồng Chat

Đọc:

```text
api/v1/chat.py
services/langgraph_orchestrator.py
services/scaffolding_engine.py
utils/llm.py
```

Mục tiêu:

```text
Hiểu một tin nhắn chat được xử lý qua những lớp nào.
```

### Vòng 5: Luồng Learning/Review

Đọc:

```text
api/v1/learning.py
services/lesson_catalog.py
services/lesson_vocabulary_provider.py
services/lesson_question_generator.py
api/v1/review.py
services/sm2_scheduler.py
```

Mục tiêu:

```text
Hiểu bài học, practice, flashcard, review hoạt động thế nào.
```

### Vòng 6: Seed/Evaluation

Đọc:

```text
app/seeders/seed_processed.py
app/seeders/ingest_corpus_to_qdrant.py
docs/data layer/scraping/data_planning.md
```

Mục tiêu:

```text
Phân biệt dữ liệu runtime thật với dữ liệu seed/eval/demo.
```

## 16. Cách Xác Định Một Tính Năng Nằm Ở Đâu

Khi bạn nghe một tính năng, có thể tìm file như sau:

| Tính năng | Nên tìm ở đâu trước |
|---|---|
| Đăng nhập/đăng ký | `api/v1/auth.py`, `core/security.py`, `core/auth_dep.py` |
| Chat tutor | `api/v1/chat.py`, `services/langgraph_orchestrator.py`, `services/scaffolding_engine.py` |
| Gọi LLM | `utils/llm.py`, `services/scaffolding_engine.py` |
| Memory cá nhân | `core/mem0_client.py`, `services/personalization.py`, `services/memory_outbox.py` |
| Lưu lỗi user | `services/error_capture_service.py`, `models/personal_review.py` |
| Error DNA | `api/v1/dna.py`, `services/error_dna_aggregator.py`, `models/error_dna.py` |
| Bài học | `api/v1/learning.py`, `services/lesson_catalog.py` |
| Sinh câu hỏi | `services/lesson_question_generator.py` |
| Flashcard/review | `api/v1/review.py`, `services/sm2_scheduler.py` |
| Dashboard tiến độ | `api/v1/analytics.py`, `services/progress_analytics.py` |
| Mood | `api/v1/mood.py`, `models/mood.py`, `services/langgraph_orchestrator.py` |
| Morning brief | `api/v1/brief.py` |
| GDPR/delete data | `api/v1/gdpr.py`, `api/v1/user.py`, `models/delete_request.py` |
| Admin dashboard | `api/v1/admin.py` |
| Seed data | `app/seeders/seed_processed.py` |

## 17. Cách Đọc Một Folder Nhỏ

Khi vào một folder, đừng đọc từng dòng ngay. Hãy hỏi:

```text
1. Folder này thuộc nhóm nào: api, core, models, services, seeders, utils?
2. File này tên gì?
3. Tên file gợi ý tính năng gì?
4. File này import gì từ folder khác?
5. File này expose hàm/class nào cho nơi khác dùng?
```

Ví dụ với:

```text
app/api/v1/chat.py
```

Ta đọc top-down:

```text
Folder api/v1
  -> đây là endpoint HTTP

File chat.py
  -> nhóm API chat

Import services/langgraph_orchestrator.py
  -> chat gọi pipeline LangGraph

Import services/error_capture_service.py
  -> chat có lưu lỗi cá nhân

Import core/redis_client.py
  -> chat có session Redis

Import models/session_log.py
  -> chat có ghi log DB
```

Chỉ cần nhìn import, bạn đã hiểu gần một nửa vai trò của file.

## 18. Sau Top-Down Thì Đi Vào Chi Tiết Như Thế Nào?

Sau khi hiểu folder, bạn mới nên đọc chi tiết theo luồng:

```text
Route nào nhận request?
  -> Schema nào validate request?
  -> Dependency nào được inject?
  -> Service nào được gọi?
  -> Model nào được đọc/ghi?
  -> Response trả bằng schema nào?
```

Ví dụ với chat:

```text
api/v1/chat.py
  -> @router.post("/chat")
  -> ChatRequest
  -> get_db + get_session_store
  -> _chat_impl()
  -> run_chat_pipeline()
  -> scaffolding_engine()
  -> SessionLog/UserErrorEvent/Redis session
  -> ChatResponse
```

## 19. Tóm Tắt Cực Ngắn

Nếu chỉ nhớ một điều:

```text
src/backend/app/main.py
  là nơi app bắt đầu.

app/api/v1/
  là nơi frontend gọi vào.

app/core/
  là hạ tầng dùng chung.

app/models/
  là hình dạng dữ liệu.

app/services/
  là logic nghiệp vụ thật.

app/seeders/
  là dữ liệu mẫu/eval/demo.

alembic/
  là lịch sử schema database.

tests/
  là nơi mô tả hành vi kỳ vọng.
```

Đọc backend top-down nghĩa là:

```text
Biết thư mục làm gì
  -> biết file làm gì
  -> biết file nào liên quan nhau
  -> sau đó mới đọc từng hàm.
```
