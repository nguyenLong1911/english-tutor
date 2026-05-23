Dựa trên tài liệu Phân tích thị trường, Đặc tả yêu cầu dự án (PRD) và hướng dẫn từ hình ảnh đính kèm, dưới đây là bản kế hoạch thu thập dữ liệu cho dự án **Agentic Language Tutor (Trợ lý học ngoại ngữ trí nhớ dài hạn)**.

# ---

**KẾ HOẠCH THU THẬP VÀ CHUẨN BỊ DỮ LIỆU (DATA PIPELINE PLAN)**

## **1\. Mục tiêu và Đối tượng dữ liệu**

Để giải quyết các "căn bệnh" như Bệnh Nghẽn (🔴), Bệnh Quên (🟡) và xây dựng "Trí nhớ dài hạn", hệ thống cần 3 nhóm dữ liệu chính:

* **Dữ liệu tri thức nền tảng:** Lỗi sai phổ biến của người Việt, cấu trúc ngữ pháp $i+1$.

* **Dữ liệu ngữ cảnh chuyên ngành:** Phục vụ tính năng Context Injection (Marketing, IT, Finance...).

* **Dữ liệu tương tác người dùng:** Để huấn luyện bộ nhớ Mem0 và Error DNA.

## **2\. Danh mục dữ liệu cần thu thập**

| Loại dữ liệu | Chi tiết nội dung | Nguồn dự kiến | Phương pháp thu thập |
| :---- | :---- | :---- | :---- |
| **Common Errors** | Danh sách lỗi ngữ pháp, từ vựng thường gặp của người Việt (Prepositions, Articles, Tenses...). | Các nghiên cứu ngôn ngữ (IJESSR, ARC Journals), Kaggle, HuggingFace. | Public datasets & Manual collection từ tài liệu nghiên cứu. |
| **Industry Vocab** | Từ vựng, mẫu câu, email mẫu thuộc các ngành: Marketing, IT, Finance, Healthcare. | LinkedIn, tài liệu chuyên ngành mở, API từ vựng chuyên ngành. | Web scraping & LLM-generated samples (Synthetic data). |
| **IELTS Data** | Đề và bài mẫu IELTS Writing Task 2, tiêu chí chấm điểm để đối chiếu. | Cambridge IELTS, các trang EdTech mở. | Manual collection & OCR (nếu là file ảnh/PDF). |
| **Pedagogical Prompts** | Các kịch bản Scaffolding (gợi ý từng bước), câu hỏi gợi mở. | Chuyên gia sư phạm (Nhóm dự án) \+ LLM. | Data augmentation (sử dụng GPT-4o để tạo biến thể). |
| **Mood & Pattern** | Dữ liệu về trạng thái cảm xúc và nhịp độ học tập (5 mức năng lượng). | Giả lập từ User Persona (Minh \- Marketing). | Synthetic data generation để validate logic ban đầu. |

## **3\. Quy trình thực hiện (Data Pipeline)**

### **Bước 1: Thu thập (Collection)**

* Sử dụng **Python Scrapy/BeautifulSoup** để thu thập danh sách lỗi sai và tài liệu chuyên ngành.

* Tận dụng **OpenAI API (GPT-4o-mini)** để tạo ra 1.000 \- 2.000 mẫu hội thoại giả lập cho giai đoạn Alpha Test.

### **Bước 2: Xử lý & Làm sạch (Cleaning & Processing)**

* **PII Scrubbing:** Loại bỏ thông tin cá nhân (tên, email thực) trước khi nạp vào Mem0 để đảm bảo bảo mật.

* **Formatting:** Chuyển đổi dữ liệu về dạng **JSON Fact Schema** (phù hợp với Mem0) bao gồm: fact\_type, content, importance\_score.

* **Deduplication:** Loại bỏ các lỗi sai trùng lặp để tối ưu không gian Vector DB.

### **Bước 3: Kiểm chứng (Validation)**

* Thực hiện **Stress Test** trên trục DATA: Kiểm tra phản hồi của AI khi lượng dữ liệu lỗi sai tăng lên 1.000 facts/user.

* Dùng phương pháp **Recasting** để validate xem dữ liệu gợi ý có hạ thấp được "Bộ lọc cảm xúc" (Affective Filter) hay không.

## **4\. Dự kiến đầu ra (Output)**

Theo đúng yêu cầu từ quy trình chuẩn, kết quả đầu ra bao gồm:

### **A. Dataset đã xử lý (Processed Datasets)**

1. **V-English Error Bank:** \~500 loại lỗi phổ biến kèm giải thích sư phạm (Scaffolding hints).  
2. **Industry Context Library:** Bộ dữ liệu từ vựng và tình huống cho 5 ngành trọng điểm (IT, Marketing, Sales, Finance, Education).  
3. **Mem0 Initial Facts:** Bộ fact mẫu cho 3 User Persona (First-timer, Speed Runner, QA Destroyer).

### **B. Tài liệu Data Pipeline (Data Pipeline Doc)**

* **Nguồn:** Chi tiết các link Kaggle, HuggingFace và tài liệu nghiên cứu ngôn ngữ học đã trích xuất.  
* **Cách Collect:** Mô tả script crawl dữ liệu và các prompt dùng để generate synthetic data.  
* **Cách Clean:** Quy trình chuẩn hóa text, loại bỏ nhiễu và định dạng vector hóa (Embedding model dự kiến: OpenAI text-embedding-3-small).

---

Kế hoạch này bám sát lộ trình Sprint 1 (Tuần 1-2) của dự án để đảm bảo hạ tầng RAG hoạt động ổn định.

