Dựa trên PRD v2, kế hoạch dữ liệu của **Agentic Language Tutor** cần tách rõ hai lớp dữ liệu:

1. **Dữ liệu runtime**: dữ liệu phát sinh từ người học và được hệ thống dùng trực tiếp khi vận hành.
2. **Dữ liệu evaluation/benchmark/seed**: dữ liệu tĩnh dùng để kiểm thử, đánh giá, benchmark và demo; không phải điều kiện để LLM biết nhận diện lỗi hoặc dạy theo nghiệp vụ sư phạm.

# ---

**KẾ HOẠCH CHUẨN BỊ DỮ LIỆU EVALUATION/SEED (DATA PIPELINE PLAN)**

## **1. Mục tiêu và đối tượng dữ liệu**

Với LLM hiện đại như Gemini/GPT/Claude, năng lực nhận diện lỗi tiếng Anh, giải thích ngữ pháp và scaffold phản hồi chủ yếu đến từ **system prompt, LangGraph workflow, memory cá nhân hóa và context của phiên học**. Vì vậy, data layer không nên được hiểu là phải thu thập thật nhiều dữ liệu tĩnh để agent mới "biết dạy".

### **1.1. Dữ liệu runtime cần thiết cho hệ thống**

Đây là dữ liệu bắt buộc để sản phẩm đáp ứng PRD về trí nhớ dài hạn, cá nhân hóa và tiến độ học:

* **User profile:** trình độ CEFR, ngành nghề, mục tiêu, thời gian học ưu tiên.
* **Session/chat data:** lượt hội thoại, intent, phản hồi, trạng thái bài học, lịch sử phiên gần đây.
* **User error events:** lỗi thực tế người học mắc, câu gốc, câu sửa, error dimension/subtype, confidence.
* **Memory facts:** facts được ghi vào Mem0/Postgres như `error_pattern`, `vocabulary`, `goal`, `progress`, `mood_pattern`, `industry_vocab`.
* **Review/progress data:** lịch SM-2, từ đã học, độ chính xác, review count, mastery state.
* **Mood/context data:** mood check-in, pasted work context, extracted terms, privacy-safe metadata.

Nhóm này là **source of truth của runtime**. Error DNA, Morning Brief, Spaced Repetition, Progress Dashboard và cá nhân hóa đều phải ưu tiên dữ liệu người dùng phát sinh thật.

### **1.2. Dữ liệu evaluation/benchmark/seed**

Các dataset tĩnh như Common Errors, Industry Vocab, IELTS samples, Pedagogical Prompts, Mood samples và Mem0 Initial Facts phục vụ các mục tiêu sau:

* Đánh giá agent có phát hiện lỗi đúng không.
* Regression test khi đổi model, system prompt hoặc LangGraph node.
* Benchmark memory retrieval, Error DNA aggregation và stress test với nhiều facts.
* Tạo dữ liệu demo/seed trước khi có đủ dữ liệu người dùng thật.
* Chuẩn hóa quality gate cho alpha mà không phụ thuộc vào production traffic.

Nhóm này **không phải nguồn sống chính của hệ thống** và không được xem là điều kiện bắt buộc để agent nhận diện lỗi hoặc sinh phản hồi sư phạm.

## **2. Danh mục dữ liệu tham chiếu để đánh giá/kiểm thử**

| Loại dữ liệu | Vai trò chính | Nguồn dự kiến | Phương pháp chuẩn bị |
| :---- | :---- | :---- | :---- |
| **Common Errors / Error Bank** | Gold/seed set để đánh giá error detection, Error DNA mapping và chất lượng giải thích. | Nghiên cứu ngôn ngữ, JFLEG/Kaggle/HuggingFace, review thủ công. | Public datasets, rule extraction, manual/teacher review. |
| **Industry Vocab** | Test Context Injection và kiểm tra agent xử lý ngữ cảnh ngành nghề. | Wikipedia glossary, tài liệu chuyên ngành mở, seed nội bộ. | Targeted collection, cleaning, schema validation. |
| **IELTS Data** | Bộ mẫu để kiểm thử writing feedback và examiner-style calibration. | Nguồn public hợp lệ, dữ liệu tự tạo/synthetic, manual seed. | Manual collection, synthetic generation, length/quality gate. |
| **Pedagogical Prompts** | Benchmark style scaffolding, Socratic questions và i+1 hinting. | Chuyên gia sư phạm + LLM generation. | Data augmentation, rubric-based validation. |
| **Mood & Pattern Samples** | Test mood-adaptive routing trước khi có mood data thật. | Persona giả lập từ PRD. | Synthetic data generation và logic validation. |
| **Mem0 Initial Facts** | Seed/stress dataset để benchmark retrieval, compaction và personalization. | Persona giả lập, synthetic conversations. | Synthetic facts, PII scrubbing, schema validation. |

## **3. Quy trình thực hiện (Evaluation Data Pipeline)**

### **Bước 1: Chuẩn bị nguồn tham chiếu**

* Chỉ thu thập dữ liệu tĩnh khi dữ liệu đó phục vụ benchmark, regression test hoặc demo rõ ràng.
* Ưu tiên nguồn hợp lệ, nhỏ, có provenance và dễ kiểm chứng thay vì scraping rộng.
* IELTS/public content phải được xử lý thận trọng về bản quyền; synthetic/manual seed được ưu tiên cho alpha.

### **Bước 2: Xử lý & làm sạch**

* **PII Scrubbing:** Loại bỏ tên, email, số điện thoại và dữ liệu nhạy cảm trước khi dùng làm seed/eval.
* **Formatting:** Chuẩn hóa về schema Pydantic/JSON để test tự động có thể chạy ổn định.
* **Deduplication:** Loại bỏ bản ghi trùng hoặc nhiễu để kết quả benchmark không bị lệch.
* **Provenance:** Lưu nguồn, phương pháp tạo và trạng thái review để phân biệt curated, auto-extracted và synthetic.

### **Bước 3: Kiểm chứng**

* Chạy schema validation cho toàn bộ processed datasets.
* Chạy quality gate cho các bộ benchmark trước khi dùng trong báo cáo alpha.
* Chạy regression tests khi đổi prompt/model/workflow.
* Chạy Mem0 retrieval/load benchmark ở quy mô PRD `1,000-2,000 facts/user`; seed data nhỏ không thay thế benchmark này.

## **4. Dự kiến đầu ra (Output)**

### **A. Evaluation/Seed Datasets**

1. **V-English Error Bank:** bộ lỗi tham chiếu để test error detection, explanation và Error DNA.
2. **Industry Context Library:** bộ từ vựng/ngữ cảnh ngành nghề để test Context Injection và domain grounding.
3. **IELTS Writing Samples:** bộ mẫu viết để test writing feedback/calibration.
4. **Pedagogical Prompt Samples:** bộ tình huống scaffold để test phong cách phản hồi.
5. **Mood Pattern Samples:** bộ mẫu mood để test session adaptation.
6. **Mem0 Initial Facts:** seed facts cho persona/test retrieval, không đại diện cho production memory.

### **B. Data Pipeline Documentation**

* **Nguồn:** link/dataset/provenance của từng bộ evaluation.
* **Cách chuẩn bị:** script collect/extract/generate, prompt synthetic và tiêu chí review.
* **Cách clean:** chuẩn hóa text, PII scrubbing, deduplication, schema validation.
* **Cách đánh giá:** test cases, benchmark command, expected thresholds và caveats.

---

Kế hoạch này giữ data pipeline có cấu trúc nhưng đặt đúng vai trò: **runtime personalization đến từ dữ liệu người dùng thật**, còn static datasets là **công cụ đánh giá và seed**, không phải nền tảng bắt buộc để agent biết dạy tiếng Anh.
