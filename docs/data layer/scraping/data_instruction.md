# **Kiến trúc Triển khai Chi tiết Hệ thống Tác tử AI Tự hành trong Thu thập, Chuẩn bị và Kiểm chuẩn Dữ liệu Lỗi Ngữ pháp ESL Việt-Anh**

## **Tối ưu hóa Tầng Thu thập Dữ liệu Học thuật và Quản lý Ngân sách Token**

### **Chuyển dịch từ Naive Scraping sang Targeted Scraping**

Bản kế hoạch thu thập dữ liệu thô sơ (naive approach) thường khiến cho các tác tử trí tuệ nhân tạo (AI agents) tự hành sụp đổ khi đưa vào vận hành thực tế do sự mất cân bằng nghiêm trọng giữa cấu trúc dữ liệu đầu vào và đầu ra mong muốn.1 Thay vì tiếp cận theo hướng tối ưu hóa dữ liệu dựa trên lược đồ đầu ra (schema-first design), các hệ thống sơ khai thường cố gắng tải toàn bộ tài liệu HTML hoặc Markdown thô của các trang web vào cửa sổ ngữ cảnh của Mô hình Ngôn ngữ Lớn (LLM).1 Hành vi này tạo ra sự lãng phí tài nguyên token khổng lồ, khi một trang web chứa 500KB mã HTML rác chỉ chứa chưa đầy 2KB thông tin ngữ nghĩa thực sự hữu ích.1 Sự quá tải này không chỉ làm tăng chi phí vận hành mà còn gây ra hiện tượng nhiễu thông tin, làm suy giảm nghiêm trọng khả năng suy luận logic của tác tử khi các tín hiệu ngôn ngữ học quan trọng bị chôn vùi trong mã nguồn phức tạp.1 Để tối ưu hóa quá trình này, tác tử AI cần phải được thiết kế dựa trên triết lý cào dữ liệu mục tiêu (Targeted Scraping), kết hợp giữa việc tối giản hóa mã nguồn tại tầng trích xuất và áp dụng các công cụ thu thập chuyên biệt.1

### **Đặc tính Kỹ thuật và Lựa chọn Công cụ cào Dữ liệu**

Các công cụ cào dữ liệu hiện đại đóng vai trò là tầng giao diện máy tính \- tác tử (Agent-Computer Interface \- ACI), giúp chuyển đổi thế giới web phi cấu trúc thành các cấu trúc tài liệu sạch mà LLM có thể dễ dàng tiếp thu.3 Việc lựa chọn công cụ phải dựa trên các đặc tính kỹ thuật về khả năng kết nối, kiểm soát và hiệu suất tài chính.4

| Tiêu chí So sánh | Firecrawl | Jina Reader (Reader API) | Crawl4AI |
| :---- | :---- | :---- | :---- |
| **Mô hình Triển khai** | Dịch vụ đám mây được quản lý hoàn toàn 5 | API đám mây siêu nhẹ 5 | Thư viện mã nguồn mở tự lưu trữ 7 |
| **Cấu trúc Đầu ra** | Markdown sạch mặc định, hỗ trợ trích xuất cấu trúc JSON 6 | Markdown tối giản, tự động mô tả hình ảnh bằng mô hình đa phương thức 8 | Markdown và HTML sạch, tối ưu hóa cho phân mảnh RAG 7 |
| **Kiểm soát Trình duyệt** | Quản lý phiên trình duyệt Chromium, tương tác bằng Playwright 6 | Phụ thuộc vào các Playwright pods đám mây của nhà cung cấp 9 | Kiểm soát tuyệt đối công cụ Playwright cục bộ 5 |
| **Khả năng Quét đệ quy** | Hỗ trợ Crawl API đệ quy và Map API để khám phá sơ đồ trang 6 | Quét đơn URL, không hỗ trợ khám phá sơ đồ toàn trang 7 | Cào đồng thời không đồng bộ với hiệu suất cực cao 7 |
| **Chi phí Vận hành** | Tính theo trang (1 tín dụng/trang), phù hợp quy mô doanh nghiệp 6 | Tính theo số lượng token tiêu thụ, miễn phí 10 triệu token ban đầu 9 | Hoàn toàn miễn phí bản quyền, chỉ tốn chi phí hạ tầng tính toán 7 |
| **Cơ chế Vượt Rào cản** | Tích hợp hệ thống giải CAPTCHA và proxy xoay vòng tự động 6 | Tự động xử lý cơ bản, dễ bị chặn bởi các tường lửa bảo mật cao 8 | Đòi hỏi tự cấu hình và tích hợp proxy di động thủ công 5 |

Để tối ưu hóa lượng token tiêu thụ tại tầng trích xuất trước khi truyền dữ liệu vào mô hình ngôn ngữ, tác tử AI cần thực hiện bộ lọc thô nội dung theo thứ tự nghiêm ngặt.1 Quy trình bắt đầu bằng việc loại bỏ toàn bộ các thẻ không chứa nội dung ngữ nghĩa bao gồm thẻ \<script\>, \<style\>, \<nav\>, \<header\>, \<footer\>, các hộp thoại đồng ý cookie, các tiện ích chia sẻ mạng xã hội và nội dung thanh bên không liên quan.1 Đối với các tài liệu học thuật hoặc bài viết nghiên cứu, việc áp dụng thuật toán Readability của Mozilla là bắt buộc nhằm giữ lại duy nhất phần thân bài viết chính, giúp cắt giảm từ 60% đến 80% dung lượng token đầu vào.1 Thay vì sử dụng LLM để tóm tắt văn bản thô—một tác vụ cực kỳ tốn kém về mặt tài chính và tài nguyên tính toán—tác tử cần áp dụng cơ chế cắt ngắn (truncation) dựa trên một ngân sách token cứng (ví dụ: giới hạn tối đa 4.000 tokens) tại một ranh giới câu sạch và ghi nhận nhật ký hệ thống về sự kiện cắt giảm này.1 Cuối cùng, việc thiết kế các phiên chạy lũy tiến (incremental runs) thông qua việc lưu trữ trạng thái hàng đợi URL (visited so với unvisited) trong một cơ sở dữ liệu lưu vết sẽ ngăn chặn hoàn toàn việc cào trùng lặp và phân bổ ngân sách quét hiệu quả.1

### **Nhận thức Chỉ thị Crawler và Tôn trọng Chính sách Máy chủ**

Trong việc thiết kế tác tử AI thu thập dữ liệu học thuật và mạng xã hội, việc tôn trọng các chỉ thị điều phối từ máy chủ mục tiêu không chỉ là vấn đề đạo đức công nghệ mà còn là yếu tố kỹ thuật then chốt để bảo vệ tác tử khỏi bị chặn địa chỉ IP (IP blocking).5 Tác tử AI cần được lập trình để tự động truy cập và phân tích tệp chỉ dẫn của máy chủ đối tác.10 Tiến trình phân tích này bao gồm việc kiểm tra các quy định truyền thống trong tệp robots.txt, các thẻ meta robots trong HTML, tiêu đề phản hồi HTTP X-Robots-Tag, cũng như các tiêu chuẩn mới nổi dành riêng cho các tác tử trí tuệ nhân tạo như robots.json và ai.txt.10

Đặc biệt, tác tử phải chủ động kiểm tra sự tồn tại của các tệp văn bản cung cấp ngữ cảnh chuyên biệt cho mô hình ngôn ngữ lớn như llms.txt và llms-full.txt nhằm thu thập trực tiếp các bản tóm tắt tài liệu chất lượng cao do chính máy chủ đích biên soạn.10 Việc xử lý các chỉ thị này giúp tác tử tự điều phối tần suất truy cập một cách hợp lý, bảo vệ cấu trúc phân cấp chủ đề (topic clusters) và tối đa hóa hiệu năng cào dữ liệu mà không làm quá tải máy chủ đối tác, từ đó tối ưu hóa ngân sách thu thập của tác tử.10

## **Tầng Thiết kế Lược đồ Dữ liệu và Giải mã Ràng buộc Cấu trúc**

### **Phân cấp Các Cấp độ Định dạng Đầu ra**

Sự thất bại của các tác tử AI trong việc xuất dữ liệu có cấu trúc thường bắt nguồn từ việc dựa dẫm vào các kỹ thuật nhắc nhở lỏng lẻo.11 Tiến trình tối ưu hóa đòi hỏi sự hiểu biết sâu sắc về bốn cấp độ kiểm soát định dạng đầu ra của mô hình ngôn ngữ lớn nhằm đảm bảo tính ổn định trong môi trường sản xuất.12

* **Cấp độ 1: Định hướng dựa trên Nhắc nhở (Hope \- Hy vọng):** Hệ thống chỉ sử dụng các câu lệnh tự nhiên trong prompt (ví dụ: "Hãy trả về kết quả dưới dạng JSON").12 Phương thức này hoàn toàn không có cơ chế ràng buộc kỹ thuật, dẫn đến tỷ lệ lỗi cú pháp và hiện tượng trôi lệch định dạng cực cao khi mô hình cập nhật hoặc gặp ngữ cảnh phức tạp.11  
* **Cấp độ 2: Chế độ JSON (JSON Mode):** Mô hình được ép buộc về mặt kỹ thuật để chỉ sinh ra các chuỗi ký tự có thể phân tích cú pháp bằng hàm json.loads().12 Mặc dù cú pháp JSON được đảm bảo, nhưng cấu trúc của các khóa (keys), kiểu dữ liệu của các trường và sự hiện diện của các thuộc tính bắt buộc vẫn nằm ngoài tầm kiểm soát của hệ thống, dẫn đến lỗi xử lý ở các ứng dụng hạ nguồn.11  
* **Cấp độ 3: Chế độ Lược đồ JSON (JSON Schema Mode):** Hệ thống truyền một lược đồ JSON đặc tả cấu trúc dữ liệu mong muốn tới API của mô hình.12 Mô hình sẽ cố gắng căn chỉnh nội dung đầu ra theo cấu trúc này.12 Tuy nhiên, trong các tình huống biên phức tạp, mô hình vẫn có thể vi phạm các ràng buộc kiểu dữ liệu hoặc sinh ra các trường bị thiếu.11  
* **Cấp độ 4: Giải mã Ràng buộc (Constrained Decoding \- Schema-Enforced):** Đây là cấp độ kiểm soát cao nhất được áp dụng trong môi trường sản xuất.12 Tại tầng cơ sở hạ tầng phục vụ của mô hình (serving infrastructure), xác suất của các token không khớp với lược đồ JSON đã định nghĩa sẽ bị ép về giá trị không (![][image1]) trong suốt quá trình giải mã.11 Cơ chế này loại bỏ hoàn toàn khả năng mô hình sinh ra các ký tự sai cú pháp, đảm bảo đầu ra tuân thủ tuyệt đối cấu trúc đã định.11

### **Lược đồ Pydantic Chuyên biệt cho Lỗi Ngữ pháp ESL Việt-Anh**

Đối với dự án thu thập lỗi ngữ pháp ESL của người Việt, việc thiết kế một lược đồ dữ liệu chặt chẽ là điều kiện tiên quyết để tác tử AI hoạt động chuẩn xác.1 Các nghiên cứu về ngôn ngữ học đối chiếu đã chỉ ra rằng người học Việt Nam thường mắc các lỗi hệ thống do sự chuyển di ngôn ngữ mẹ đẻ (L1 transfer) và những khác biệt căn bản trong cấu trúc ngữ pháp giữa tiếng Việt và tiếng Anh.14

Dưới đây là sơ đồ Pydantic được thiết kế chuyên biệt để phân loại và lưu trữ các thực thể lỗi ngữ pháp này, tích hợp trực tiếp các mô tả trường để hướng dẫn LLM trong quá trình sinh dữ liệu 12:

Python

from pydantic import BaseModel, Field  
from enum import Enum  
from typing import List, Optional

class ErrorCategory(str, Enum):  
    TENSE\_AND\_ASPECT \= "Tense and Aspect"  
    COPULA\_BE\_OMISSION \= "Copula Be Omission"  
    COPULA\_BE\_REDUNDANCY \= "Copula Be Redundancy"  
    ADVERB\_MISPLACEMENT \= "Adverb Misplacement"  
    WORD\_CHOICE\_LEXICAL \= "Word Choice Lexical"  
    L1\_INTERFERENCE\_STRUCTURE \= "L1 Interference Structure"  
    PUNCTUATION\_AND\_AGREEMENT \= "Punctuation and Agreement"

class ESLErrorInstance(BaseModel):  
    original\_text: str \= Field(  
       ...,  
        description="Đoạn văn gốc chứa lỗi ngữ pháp do người Việt viết, chưa qua hiệu đính."  
    )  
    corrected\_text: str \= Field(  
       ...,  
        description="Đoạn văn sau khi đã được hiệu đính chuẩn xác bởi chuyên gia bản xứ."  
    )  
    error\_category: ErrorCategory \= Field(  
       ...,  
        description="Phân loại lỗi chính xác dựa trên danh mục lỗi ESL Việt-Anh đã được định nghĩa."  
    )  
    linguistic\_explanation: str \= Field(  
       ...,  
        description="Giải thích chi tiết về mặt ngôn ngữ học, chỉ rõ ảnh hưởng của cấu trúc tiếng Việt (L1 transfer) hoặc sự nhầm lẫn trong việc áp dụng quy tắc ngữ pháp tiếng Anh."  
    )  
    cefr\_level: str \= Field(  
       ...,  
        pattern="^(A1|A2|B1|B2|C1|C2)$",  
        description="Ước lượng trình độ khung năng lực ngoại ngữ châu Âu (CEFR) của người viết lỗi ngữ pháp này."  
    )  
    confidence\_score: float \= Field(  
       ...,  
        ge=0.0,  
        le=1.0,  
        description="Điểm số tin cậy của tác tử đối với tính chính xác của phân loại lỗi này."  
    )

class ESLGrammarDatasetBatch(BaseModel):  
    source\_url: str \= Field(..., description="URL nguồn của tài liệu học thuật hoặc trang web thu thập dữ liệu.")  
    scraped\_at: str \= Field(..., description="Mốc thời gian thu thập định dạng ISO 8601.")  
    errors\_detected: List \= Field(  
       ...,  
        description="Danh sách các thực thể lỗi ngữ pháp được phát hiện và phân tích trong tài liệu văn bản."  
    )

### **Triển khai Mã nguồn và Vòng lặp Tự sửa lỗi**

Để đưa lược đồ Pydantic vào vận hành thực tế, tác tử AI cần được tích hợp với các SDK của các nhà cung cấp mô hình lớn thông qua các phương thức hỗ trợ cấu trúc đầu ra bản địa, hoặc thông qua các khung điều phối đa mô hình như LangChain.12 Mã triển khai dưới đây minh họa cách thức tích hợp lược đồ Pydantic trực tiếp vào cuộc gọi API của OpenAI và cách thiết lập một vòng lặp tự sửa lỗi (repair loop) khi xảy ra ngoại lệ xác thực nhằm đảm bảo hệ thống không bị gián đoạn đột ngột 12:

Python

import json  
from openai import OpenAI  
from pydantic import ValidationError

def execute\_structured\_extraction(prompt\_content: str, raw\_scraped\_data: str) \-\> ESLGrammarDatasetBatch:  
    client \= OpenAI()  
      
    \# Định nghĩa chỉ thị hệ thống để giảm thiểu sự phân tán token  
    system\_prompt \= (  
        "You are an expert computational linguist specializing in Vietnamese-English ESL grammar errors. "  
        "Analyze the provided text, extract all grammatical errors, and return strictly formatted JSON "  
        "conforming to the provided schema. Do not include any external text or markdown formatting fences."  
    )  
      
    try:  
        \# Sử dụng API phân tích cú pháp trực tiếp dựa trên Pydantic ở Cấp độ 4  
        response \= client.beta.chat.completions.parse(  
            model="gpt-4o",  
            messages=,  
            response\_format=ESLGrammarDatasetBatch,  
            temperature=0.0 \# Thiết lập nhiệt độ bằng 0 để giải mã xác định \[16\]  
        )  
        return response.choices.message.parsed  
          
    except ValidationError as val\_err:  
        \# Kích hoạt vòng lặp tự sửa lỗi khi dữ liệu không vượt qua tầng xác thực của Pydantic \[16\]  
        raw\_invalid\_json \= response.choices.message.content  
        repair\_prompt \= (  
            f"The previous output failed Pydantic validation with the following errors:\\n{str(val\_err)}\\n"  
            f"Here is the invalid JSON output generated:\\n{raw\_invalid\_json}\\n"  
            f"Correct the JSON structure and return ONLY valid JSON matching the schema perfectly."  
        )  
          
        repair\_response \= client.beta.chat.completions.parse(  
            model="gpt-4o",  
            messages=\[  
                {"role": "system", "content": system\_prompt},  
                {"role": "user", "content": repair\_prompt}  
            \],  
            response\_format=ESLGrammarDatasetBatch,  
            temperature=0.0  
        )  
        return repair\_response.choices.message.parsed

## **Đường ống Lọc và Khử Thông tin Nhạy cảm Đa tầng**

### **Giới hạn của Regex và Thiết lập Thuật toán Luhn**

Một sai lầm phổ biến khi xây dựng các tác tử thu thập dữ liệu là sử dụng các biểu thức chính quy (regular expressions) thô sơ để lọc và loại bỏ thông tin nhạy cảm cá nhân (Personally Identifiable Information \- PII) như số điện thoại, email, hoặc số thẻ học viên.17 Biểu thức chính quy thuần túy thường tạo ra tỷ lệ dương tính giả rất lớn trong môi trường thực tế, khiến cho nhiều cấu trúc câu mang ý nghĩa học thuật bị redaction nhầm, làm mất đi giá trị phân tích lỗi ngữ pháp.18 Ví dụ, một chuỗi ký tự chứa mã số học viên 16 chữ số ngẫu nhiên dễ dàng kích hoạt bộ lọc thẻ tín dụng của Regex.18

Để khắc phục giới hạn này, tác tử AI cần phải kết hợp Regex với các tầng kiểm chuẩn logic toán học.18 Điển hình là việc áp dụng thuật toán Luhn (checksum) làm cổng chặn (gate) đối với các số định danh hoặc số tài khoản học vụ được cào từ các kho lưu trữ trực tuyến nhằm đảm bảo tính hợp lệ thực tế trước khi kích hoạt bộ lọc redaction.18 Ngoài ra, bộ lọc Regex cần phải tích hợp các quy tắc loại trừ nghiêm ngặt đối với các dải số chưa từng được phát hành hoặc các dải số dự phòng đặc thù của các quốc gia nhằm tránh loại bỏ nhầm các cấu trúc số mang tính ví dụ trong bài viết.18

### **Kiến trúc Lọc đa tầng Sentinel và Microsoft Presidio**

Trong các hệ thống xử lý ngôn ngữ tự nhiên cấp doanh nghiệp, đường ống lọc PII phải hoạt động như một tầng bảo vệ tiền tuyến (Sentinel), chặn lọc dữ liệu ngay khi nó đi vào hệ thống và trước khi bất kỳ tác vụ nhúng vectơ (embedding) hay suy luận mô hình nào được thực hiện.18 Kiến trúc này kết hợp sức mạnh của cả ba phương pháp tiếp cận: bộ lọc dựa trên quy tắc (Rule-based Regex) cho các định dạng cố định, mô hình Nhận diện Thực thể có Tên (Named Entity Recognition \- NER) từ thư viện Microsoft Presidio cho các thực thể ngữ cảnh tự nhiên như tên học viên, địa chỉ, trường học, và cuối cùng là tầng suy luận ngữ nghĩa sâu của LLM cho các PII ẩn dụ.19

Sự phối hợp này cho phép nhận diện các thực thể nhạy cảm mang tính gián tiếp mà Regex hay NER truyền thống thường bỏ sót, ví dụ như câu "Trợ lý của Hiệu trưởng trường Đại học Ngoại thương vừa thông báo về bài luận của học viên đạt giải Nhất cuộc thi Orion".20 Ở đây, cụm từ "Trợ lý của Hiệu trưởng" và "giải Nhất cuộc thi Orion" kết hợp với nhau có thể gián tiếp tiết lộ danh tính học viên trong một nhóm nhỏ.20

### **Tác động của Khử PII tới Nhúng Vectơ và Truy xuất RAG**

Việc khử thông tin nhạy cảm trước khi nạp dữ liệu lỗi ngữ pháp vào các kho lưu trữ tri thức mang lại những lợi ích kỹ thuật vượt trội ngoài phạm vi tuân thủ pháp lý.20 Trong các hệ thống Tìm kiếm Phản hồi Tăng cường (RAG), các mô hình nhúng vectơ biểu diễn ngữ nghĩa của câu dựa trên toàn bộ các mã thông báo (tokens) hiện diện.20 Sự xuất hiện của các tên riêng Việt Nam đặc thù (như "Nguyễn Văn A" hay "Trần Thị B") hoặc các địa danh cụ thể có thể tạo ra các nhiễu loạn phân bổ trong không gian vectơ, khiến các câu có cùng loại lỗi ngữ pháp nhưng khác tên nhân vật bị đẩy ra xa nhau trong không gian biểu diễn.20

Bằng cách thay thế toàn bộ PII bằng các nhãn định danh chuẩn hóa như \`\`, hệ thống nhúng sẽ chỉ tập trung vào cấu trúc cú pháp và các thành phần từ loại của câu.20 Điều này giúp giảm thiểu sự sai lệch trong biểu diễn không gian vectơ (embedding bias) và cải thiện rõ rệt độ chính xác của việc truy xuất ngữ nghĩa (retrieval recall) khi tác tử AI tìm kiếm các mẫu lỗi ngữ pháp tương đồng trong cơ sở dữ liệu.20

Để quản lý hiệu quả các chiến lược khử thông tin nhạy cảm, tác tử AI cần được cấu hình cụ thể theo bảng dưới đây nhằm áp dụng đúng phương thức xử lý cho từng loại dữ liệu khác nhau 17:

| Loại PII phát hiện | Phương thức Xử lý | Mô tả Kỹ thuật | Trường hợp Sử dụng trong Dự án ESL | Mục tiêu Tuân thủ |
| :---- | :---- | :---- | :---- | :---- |
| **Tên học viên / Giáo viên** | REDACT | Thay thế thực thể bằng nhãn chuẩn hóa có hậu tố ngẫu nhiên (ví dụ: \`\`).18 | Loại bỏ danh tính học viên trong các bài viết mẫu hoặc bài thi viết.20 | GDPR, HIPAA 17 |
| **Email / Số điện thoại** | MASK | Ẩn một phần ký tự hiển thị, chỉ giữ lại định dạng cơ bản để nhận biết cấu trúc lỗi liên quan đến email/SĐT.17 | Sử dụng khi học viên viết thông tin liên lạc giả định trong phần viết thư của bài thi.18 | SOC 2 18 |
| **Mã số học viên / CCCD** | HASH | Mã hóa một chiều bằng thuật toán SHA-256 kết hợp mã khóa bí mật (Salt) để bảo toàn tính độc nhất.17 | Giúp theo dõi tiến trình sửa lỗi của cùng một học viên qua nhiều bài viết mà không tiết lộ danh tính.20 | PCI-DSS, GDPR 18 |
| **Mã lớp học / Học viện** | PSEUDONYMIZE | Thay thế bằng một tên giả định ngẫu nhiên từ danh sách được ánh xạ cố định trong bảng quản lý.18 | Loại bỏ yếu tố định danh đơn vị đào tạo để bảo vệ tính ẩn danh của dữ liệu nghiên cứu.20 | SOC 2, HIPAA 18 |

## **Thiết kế Kiến trúc Tự phục hồi và Kiểm soát Độ trễ Hệ thống**

### **Phân loại Lỗi và Cơ chế Exponential Backoff có Jitter**

Trong môi trường vận hành liên tục, tác tử AI tự hành sẽ thường xuyên đối mặt với các sự cố kết nối và vượt ngưỡng giới hạn yêu cầu (rate limits) từ phía nhà cung cấp mô hình ngôn ngữ lớn hoặc các máy chủ cào dữ liệu mục tiêu.22 Để đảm bảo tính bền vững của hệ thống, tác tử cần phải phân loại chính xác các lỗi nhận được từ các phản hồi HTTP và các ngoại lệ hệ thống thành hai nhóm riêng biệt.23

* **Nhóm Lỗi Tạm thời (Transient Errors \- Có thể thử lại):** Bao gồm mã trạng thái HTTP 429 (Too Many Requests), HTTP 408 (Request Timeout), các lỗi máy chủ HTTP 5xx (500, 502, 503, 504), các sự cố ngắt kết nối socket hoặc ngắt kết nối TCP đột ngột.23 Đây là các sự cố mang tính thời điểm và hệ thống có khả năng tự phục hồi khi thực hiện lại yêu cầu sau một khoảng thời gian chờ hợp lý.23  
* **Nhóm Lỗi Vĩnh viễn (Permanent Errors \- Không được thử lại):** Bao gồm mã trạng thái HTTP 400 (Bad Request \- lỗi cú pháp hoặc tham số yêu cầu sai), HTTP 401 (Unauthorized \- khóa API không hợp lệ), HTTP 403 (Forbidden \- không có quyền truy cập), HTTP 499 (Client Closed Request \- kết nối bị đóng chủ động từ phía khách khách), và các lỗi liên quan đến việc vượt quá giới hạn độ dài ngữ cảnh tối đa của mô hình (Context Length Error).23 Việc thử lại vô điều kiện đối với nhóm lỗi này sẽ tạo ra một vòng lặp vô hạn gây lãng phí tài nguyên tính toán và có nguy cơ khiến tài khoản hệ thống bị khóa.24

Đối với các lỗi tạm thời, việc gửi lại yêu cầu ngay lập tức (immediate retry) là một phản mẫu (anti-pattern) nguy hiểm, dễ tạo ra hiện tượng cascading failures và làm trầm trọng thêm tình trạng quá tải của máy chủ mục tiêu.22 Do đó, tác tử phải áp dụng thuật toán Chờ đợi tăng dần theo số mũ kết hợp dao động ngẫu nhiên (Exponential Backoff with Jitter) để tính toán thời gian trễ giữa các lần thử lại.22

Thời gian trễ ![][image2] được xác định thông qua công thức toán học dưới đây:

![][image3]  
Trong đó, ![][image4] là khoảng thời gian trễ nền ban đầu (thường được thiết lập là ![][image5] giây), ![][image6] là giới hạn trễ tối đa để bảo vệ độ trễ hệ thống (thường đặt là ![][image7] giây), ![][image8] là số lần đã thực hiện thử lại thất bại trước đó, và ![][image9] là một giá trị nhiễu ngẫu nhiên (ví dụ từ ![][image10] đến ![][image5] giây).22 Việc thêm tham số nhiễu ngẫu nhiên này có ý nghĩa sống còn trong việc ngăn chặn hiện tượng "bầy đàn" (thundering herd problem), trong đó hàng loạt tác tử cào dữ liệu đồng thời gửi yêu cầu thử lại tại cùng một thời điểm vật lý, gây nghẽn mạng cục bộ.22

### **Khai báo Chính sách Resiliency với Dapr và Tenacity**

Để đơn giản hóa việc triển khai cơ chế kháng lỗi trong mã nguồn tác tử, kỹ sư hệ thống có thể tận dụng các chính sách resiliency khai báo của Dapr hoặc sử dụng thư viện Tenacity trực tiếp trong Python.22

Dưới đây là bảng đặc tả cấu hình các tham số kháng lỗi và quản lý kết nối tối ưu cho tác tử AI thu thập dữ liệu ESL, tích hợp các cấu hình kết nối cơ sở dữ liệu pgvector để đảm bảo tính ổn định của luồng ghi dữ liệu đồng thời 26:

| Tham số Cấu hình | Giá trị Cấu hình | Giải thích Kỹ thuật và Tác động đến Hệ thống |
| :---- | :---- | :---- |
| **max\_retries** | 5 | Số lần thử lại tối đa cho một yêu cầu bị lỗi tạm thời trước khi chính thức đánh dấu thất bại và chuyển sang cơ chế suy giảm chất lượng dịch vụ (graceful degradation).22 |
| **initial\_delay** | 1.0s | Khoảng thời gian chờ ban đầu trước khi thực hiện lần thử lại đầu tiên (![][image4]).24 |
| **max\_delay** | 60.0s | Ngưỡng giới hạn thời gian trễ tối đa giữa các lần thử lại để tránh kéo dài thời gian xử lý của tác tử quá mức chấp nhận được.23 |
| **request\_timeout** | 60.0s | Thời gian tối đa cho phép một cuộc gọi API mô hình ngôn ngữ lớn hoặc một tác vụ cào dữ liệu hoạt động trước khi tự động ngắt kết nối và kích hoạt lỗi timeout.25 |
| **circuit\_breaker\_threshold** | 0.5 | Ngưỡng kích hoạt bộ ngắt mạch. Nếu tỷ lệ yêu cầu thất bại liên tục vượt quá 50% trong một cửa sổ thời gian xác định, toàn bộ luồng gọi API sẽ bị ngắt hoàn toàn để bảo vệ hệ thống.25 |
| **pgvector\_min\_connections** | 10 | Số lượng kết nối tối thiểu được duy trì liên tục trong bể kết nối (connection pool) của pgvector để phục vụ các tác vụ ghi dữ liệu tức thì của tác tử.26 |
| **pgvector\_max\_connections** | 20 | Giới hạn kết nối tối đa cho phép của bể kết nối pgvector nhằm ngăn chặn việc làm cạn kiệt tài nguyên kết nối của máy chủ cơ sở dữ liệu khi hệ thống cào dữ liệu đồng thời ở quy mô lớn.26 |

Đối với các phương thức thanh toán của nhà cung cấp mô hình (như Vertex AI), việc điều chỉnh chính sách thử lại cần phải tương thích với gói dịch vụ sử dụng.24 Khi tác tử hoạt động dưới gói Flex Pay-as-you-go vốn có độ ưu tiên thấp và tốc độ xử lý chậm hơn, việc tăng giới hạn thời gian chờ yêu cầu (timeout) lên 30 phút là cần thiết để cho phép máy chủ hoàn thành các tác vụ phân tích ngôn ngữ phức tạp thay vì liên tục kích hoạt cơ chế thử lại.24 Ngược lại, đối với gói Priority Pay-as-you-go hoặc Provisioned Throughput, các lỗi 429 nhận được thường biểu thị việc hệ thống đã vượt quá dung lượng băng thông đã mua, đòi hỏi tác tử phải tạm dừng luồng công việc hoặc thực hiện phân luồng tải sang các vùng máy chủ dự phòng thay vì cố gắng gửi lại yêu cầu liên tục.24

## **Kiến trúc Trí nhớ Song song và Quản lý Trạng thái Tác tử**

### **Trí nhớ Ngắn hạn và Quản lý Điểm kiểm soát Phiên**

Một trong những nguyên nhân khiến các tác tử AI tự hành thất bại trong các chuỗi tác vụ dài là hiện tượng mất dấu trạng thái suy luận khi gặp sự cố ngắt quãng kết nối giữa chừng.23 Để khắc phục triệt để, kiến trúc tác tử cần phân tách rõ ràng tầng quản lý bộ nhớ và tầng logic của mô hình ngôn ngữ lớn.27 Sự phân tách này cho phép kỹ sư hệ thống nâng cấp hoặc thay thế mô hình nền tảng (ví dụ chuyển đổi từ GPT-4o sang Claude 3.5 Sonnet) mà không cần phải tái cấu trúc lại toàn bộ hệ thống quản lý phiên và cơ chế lưu trữ của tác tử.27

Trí nhớ ngắn hạn (Short-Term Session Memory) chịu trách nhiệm duy trì trạng thái của phiên làm việc hiện tại của tác tử.27 Quy trình này được quản lý thông qua một chu trình vận hành khép kín bao gồm: lưu trữ lịch sử hội thoại và trạng thái tác tử vào bộ lưu trữ phiên (Session Store), tuần tự hóa trạng thái này thành một cấu trúc prompt chuẩn hóa, giám sát lượng token tiêu thụ trên mỗi yêu cầu, gửi yêu cầu tới mô hình, nhận phản hồi và cập nhật lại bộ lưu trữ phiên.27

Để tránh việc vượt quá giới hạn cửa sổ ngữ cảnh khi xử lý các tài liệu học thuật ESL dài, tác tử phải liên tục đếm token đầu vào và thực hiện cơ chế cắt bớt lịch sử hội thoại (truncation events).27 Trong tiến trình này, các chỉ dẫn hệ thống cốt lõi (system instructions) luôn được ưu tiên bảo vệ ở vị trí đầu tiên của cửa sổ ngữ cảnh, trong khi các phản hồi cũ hơn sẽ bị loại bỏ dần theo cơ chế hàng đợi (First-In, First-Out).27 Đồng thời, cơ chế lưu điểm kiểm soát (checkpointing) được kích hoạt một cách tự động sau mỗi bước trích xuất lỗi thành công, đảm bảo tác tử có thể khôi phục lại trạng thái làm việc chính xác tại điểm kiểm soát gần nhất trong trường hợp xảy ra sự cố sụp đổ hệ thống vật lý.27

### **Trí nhớ Dài hạn với Mem0 và Hologres Vector DB**

Trí nhớ dài hạn (Long-Term Memory) đóng vai trò tích lũy tri thức ngôn ngữ học qua nhiều phiên làm việc độc lập của tác tử, giúp tối ưu hóa hiệu suất trích xuất lỗi ngữ pháp theo thời gian.27 Hệ thống tích hợp framework Mem0 kết hợp với cơ sở dữ liệu phân tích thời gian thực Hologres để xây dựng một động cơ lưu trữ và tìm kiếm vectơ lai (hybrid search vector database).28

Kiến trúc chi tiết của tầng trí nhớ dài hạn này được mô tả thông qua sơ đồ luồng dữ liệu dưới đây 28:

   
            │  
            ▼  
┌──────────────────────────────────────────────┐  
│ Bộ Trích xuất Trí nhớ (Memory Extractor)      │ ──► Nhận diện thực thể ngôn ngữ có giá trị lâu dài   
└──────────────────────────────────────────────┘  
            │  
            ▼  
┌──────────────────────────────────────────────┐  
│ Động cơ Nhúng (Embedding Engine)             │ ──► Chuyển đổi tri thức thành vectơ cao chiều   
└──────────────────────────────────────────────┘  
            │  
            ▼  
┌──────────────────────────────────────────────┐  
│ Tầng Lưu trữ Vectơ Hologres                  │ ──► Quản lý chỉ mục HGraph và bảng dữ liệu lai   
└──────────────────────────────────────────────┘  
            ▲  
            │ (Truy vấn Top-K tương đồng ngữ nghĩa)   
┌──────────────────────────────────────────────┐  
│ Bộ Truy xuất Trí nhớ (Memory Retriever)       │ ──► Vectơ hóa truy vấn hiện tại của tác tử   
└──────────────────────────────────────────────┘  
            ▲  
            │

Bộ trích xuất trí nhớ (Memory Extractor) hoạt động như một tiến trình chạy ngầm, liên tục phân tích các kết quả hiệu đính lỗi ngữ pháp thành công.28 Khi phát hiện một mẫu lỗi ngữ pháp có tính chu kỳ hoặc một giải thích ngôn ngữ học có độ tin cậy cao, bộ trích xuất sẽ chuyển đổi thông tin này thành một thực thể tri thức chuẩn hóa.28

Động cơ nhúng sau đó sẽ chuyển hóa thực thể này thành một vectơ cao chiều và lưu trữ vào Hologres.28 Cơ sở dữ liệu này hỗ trợ lưu trữ hỗn hợp cả trường vectơ, văn bản thô và các trường định dạng vô hướng (scalar fields), sử dụng chỉ mục vectơ HGraph hiệu năng cao để thực hiện các truy vấn tương đồng ngữ nghĩa đạt độ trễ dưới mức mili-giây.28 Trước khi tác tử thực hiện một lượt phân tích văn bản mới, bộ truy xuất trí nhớ (Memory Retriever) sẽ tự động tìm kiếm các tri thức lỗi ngữ pháp tương đồng nhất trong quá khứ và chèn trực tiếp vào prompt hệ thống thông qua bộ tích hợp ngữ cảnh (Context Integrator).28 Cơ chế này giúp tác tử kế thừa kinh nghiệm từ các phiên làm việc trước đó mà không làm tăng tải trọng tính toán của mô hình ngôn ngữ.28

### **Chỉ dẫn Tùy chỉnh và Trích xuất Tri thức Đặc thù**

Để đảm bảo trí nhớ dài hạn của tác tử không bị ô nhiễm bởi các thông tin ngoài lề hoặc các đoạn trò chuyện rác từ các nguồn dữ liệu mạng xã hội, kỹ sư hệ thống cần phải cấu hình các Chỉ dẫn Tùy chỉnh (Custom Instructions) trực tiếp cho Mem0.29 Việc thiết lập các chỉ dẫn này buộc bộ trích xuất trí nhớ chỉ tập trung vào việc ghi nhớ các quy tắc cú pháp, phân loại lỗi ESL và các hiện tượng chuyển di ngôn ngữ Việt-Anh.29

Dưới đây là đoạn mã nguồn cấu hình chi tiết cho đối tượng khách của Mem0 trong Python 28:

Python

from mem0 import Memory

\# Định nghĩa chỉ dẫn tùy chỉnh nghiêm ngặt để kiểm soát tầng trích xuất trí nhớ  
custom\_instructions \= (  
    "You are a memory extraction assistant for a Vietnamese-English ESL grammar error dataset. "  
    "Your sole task is to extract domain-specific linguistic facts, including: "  
    "1. Systematic grammar error patterns made by Vietnamese learners (e.g., tense confusion, copula insertion/omission, adverb misplacement). "  
    "2. Valid linguistic explanations linking errors to L1 Vietnamese language transfer. "  
    "3. Correct English equivalents and CEFR level estimations. "  
    "Ignore all casual chatter, user meta-information, or non-linguistic data. "  
    "Always return the extracted facts as a structured JSON object with a single 'facts' array."  
)

\# Cấu hình đối tượng Mem0 tích hợp chỉ dẫn tùy chỉnh và cài đặt LLM Qwen-Plus   
config \= {  
    "llm": {  
        "provider": "openai",  
        "config": {  
            "openai\_base\_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",  
            "api\_key": "YOUR\_DASHSCOPE\_API\_KEY",  
            "model": "qwen-plus",  
            "temperature": 0.2,  
            "max\_tokens": 2000,  
            "top\_p": 1.0  
        }  
    },  
    "custom\_instructions": custom\_instructions  
}

\# Khởi tạo đối tượng quản lý bộ nhớ từ cấu hình   
memory\_manager \= Memory.from\_config(config)

## **Quy trình Kỹ nghệ Tổng hợp Dữ liệu và Kiểm chuẩn Mô phỏng**

### **Chuỗi Quy trình synth-dataset-kit và NeMo Data Designer**

Bên cạnh việc thu thập các mẫu lỗi ngữ pháp thực tế từ các nguồn trực tuyến, việc mở rộng quy mô tập dữ liệu một cách chủ động thông qua quy trình tổng hợp dữ liệu mô phỏng (synthetic data generation) là giải pháp bắt buộc để đạt được số lượng mẫu lớn cho việc huấn luyện tinh chỉnh mô hình.30 Tuy nhiên, các kỹ thuật sinh dữ liệu mô phỏng đơn giản (ví dụ viết prompt yêu cầu LLM tự viết ra câu lỗi và câu sửa) thường tạo ra các mẫu dữ liệu nghèo nàn, lặp lại cấu trúc ngữ pháp và thiếu tính thực tế so với hành vi ngôn ngữ học thực tế của người Việt.30

Để giải quyết vấn đề này, hệ thống cần triển khai một quy trình kỹ nghệ dữ liệu mô phỏng đa tầng sử dụng các thư viện chuyên nghiệp như synth-dataset-kit hoặc NVIDIA NeMo Data Designer.30 Quy trình này chuyển dịch hoàn toàn từ việc "tạo dữ liệu" (generation) sang "kỹ nghệ dữ liệu" (data engineering).32

Sự khác biệt căn bản giữa hai phương pháp tiếp cận được trình bày cụ thể trong bảng so sánh dưới đây 30:

| Thuộc tính Quy trình | Phương pháp Sinh dữ liệu Đơn giản (Naive Generation) | Phương pháp Kỹ nghệ Dữ liệu Mô phỏng (Synthetic Data Engineering) |
| :---- | :---- | :---- |
| **Kiến trúc Luồng công việc** | Một bước duy nhất: Prompt ![][image11] LLM ![][image11] Lưu kết quả.32 | Chuỗi quy trình đa tầng: Seed Sampling ![][image11] Expansion ![][image11] LLM-as-a-Judge ![][image11] Decontamination ![][image11] Lưu kết quả.32 |
| **Kiểm soát Độ đa dạng** | Phụ thuộc hoàn toàn vào tính ngẫu nhiên của tham số nhiệt độ (temperature) của mô hình.30 | Kiểm soát đa dạng hóa thông qua việc lấy mẫu ngẫu nhiên có kiểm soát các thuộc tính mầm (seed attributes) trước khi gọi LLM.30 |
| **Độ chính xác Cú pháp** | Không có cơ chế kiểm chuẩn tự động, dễ bị trôi lệch định dạng JSON gây lỗi phân tích.32 | Tích hợp sẵn tầng kiểm tra định dạng và sửa lỗi tự động, đảm bảo 100% dữ liệu đầu ra hợp lệ về mặt cấu trúc.32 |
| **Đảm bảo Chất lượng** | Chấp nhận hoàn toàn mọi nội dung sinh ra từ LLM, dẫn đến nhiều dữ liệu rác hoặc lỗi không thực tế.32 | Áp dụng mô hình đánh giá độc lập (LLM-as-a-judge) chấm điểm chất lượng theo một bộ rubric tiêu chí khoa học.30 |
| **Phòng chống Rò rỉ Dữ liệu** | Dữ liệu sinh ra có thể trùng lặp nguyên văn với dữ liệu mầm hoặc dữ liệu kiểm thử.32 | Thực hiện bước kiểm tra giải nhiễm độc (decontamination check) để loại bỏ hoàn toàn các mẫu trùng lặp ngữ nghĩa.32 |

### **Thiết kế Kịch bản Đối thoại ESL và Kiểm soát Ngữ nghĩa**

Để tạo ra một tập dữ liệu lỗi ngữ pháp ESL Việt-Anh có giá trị huấn luyện cao, kịch bản sinh dữ liệu mô phỏng cần phải bắt chước chính xác các hiện tượng ngôn ngữ học đối chiếu thực tế.14

Khi lập trình tác tử AI sinh các đoạn hội thoại mô phỏng (từ 4 đến 8 lượt thoại), prompt hệ thống cần tích hợp các lý thuyết ngôn ngữ học cốt lõi để ép buộc LLM (ví dụ sử dụng mô hình chuyên dụng Nemotron 3 Nano) tái hiện các lỗi ngữ pháp hệ thống của người Việt.15 Dưới đây là các hiện tượng chuyển di ngôn ngữ học điển hình cần được đưa vào tham số hóa của prompt 14:

* **Sự nhầm lẫn và lược bỏ Thời \- Thể (Tense and Aspect):** Trong tiếng Việt, động từ không biến đổi hình thái để biểu thị thời gian mà thường dựa vào ngữ cảnh hoặc các phó từ chỉ thời gian đứng trước động từ (như "đã", "đang", "sẽ").15 Điều này dẫn đến xu hướng người Việt chuyển di nguyên văn động từ nguyên mẫu không chia sang câu tiếng Anh (ví dụ: "Yesterday I go to the market with my mother").15 Tác tử AI cần được chỉ dẫn để mô phỏng chính xác lỗi này trong các bối cảnh kể chuyện quá khứ.15  
* **Lỗi liên quan đến động từ liên kết Copula "be":** Tiếng Việt không có một cấu trúc tương đương hoàn chỉnh cho động từ "to be" khi đi kèm với tính từ.15 Câu tiếng Việt thường viết trực tiếp chủ ngữ và vị ngữ tính từ (ví dụ: "Cô ấy đẹp" \- tương đương "She beautiful").15 Do đó, người học thường mắc lỗi lược bỏ động từ "be" (Copula Omission: "She very happy today") hoặc ngược lại, mắc lỗi chèn thừa động từ "be" khi đã có động từ thường do thói quen dịch từng từ (Copula Redundancy: "I am study English every day").15  
* **Vị trí của trạng từ trong cụm động từ (Adverb Misplacement):** Trong tiếng Việt, các trạng từ chỉ tần suất hoặc tính chất thường có vị trí linh hoạt hoặc đứng trực tiếp sau động từ chính để bổ nghĩa.15 Khi chuyển dịch sang tiếng Anh, người học thường xếp đặt vị trí trạng từ sai quy tắc (ví dụ: "I studied always my lessons" hoặc "Don't drive too fastly" do thói quen thêm hậu tố "-ly" vào tính từ vô điều kiện).34  
* **Lỗi cấu trúc chuyển di L1 (L1 Interference Structure):** Điển hình là cấu trúc thừa thãi liên từ đôi (Double Conjunctions) xuất phát từ thói quen sử dụng các cặp liên từ hô ứng trong tiếng Việt như "Tuy nhiên... nhưng..." hoặc "Mặc dù... nhưng...".14 Khi dịch sang tiếng Anh, người học thường viết đồng thời cả hai liên từ trong một câu ghép (ví dụ: "Although the technique is new, but Professor Clark is optimistic about its potential").14 Đây là một lỗi cực kỳ phổ biến của học viên trình độ sơ cấp và trung cấp.14

Để kiểm soát chặt chẽ quá trình sinh dữ liệu mô phỏng, tác tử AI cần áp dụng kỹ thuật thiết lập hồ sơ người dùng (User Profiles) từ thư viện Evidently.31 Việc này cho phép cấu hình chi tiết vai trò, trình độ ngôn ngữ, tâm trạng và bối cảnh giao tiếp của học viên giả định trước khi tiến hành tạo câu.31

Đồng thời, hệ thống phải thiết lập các rào cản kỹ thuật (guardrails) nghiêm ngặt trong prompt để ngăn chặn mô hình sinh ra các đoạn hội thoại mang tính định kiến xã hội, tranh cãi chính trị hoặc chứa thông tin độc hại, đảm bảo tập dữ liệu đầu ra hoàn toàn sạch sẽ, an toàn và sẵn sàng cho việc phân phối học thuật hoặc thương mại.33 Toàn bộ dữ liệu tổng hợp cuối cùng sẽ được xuất ra dưới định dạng cấu trúc bảng dữ liệu Pandas DataFrame để dễ dàng tích hợp vào các bước kiểm thử hiệu năng mô hình sau này.31

#### **Nguồn trích dẫn**

1. How to Build a Web Scraping Skill for AI Agents: Token Reduction ..., truy cập vào tháng 5 9, 2026, [https://www.mindstudio.ai/blog/build-web-scraping-skill-ai-agents-token-reduction](https://www.mindstudio.ai/blog/build-web-scraping-skill-ai-agents-token-reduction)  
2. AI Agent Web Scraping: Data Collection and Analysis \- ScrapeGraphAI, truy cập vào tháng 5 9, 2026, [https://scrapegraphai.com/blog/ai-agent-webscraping](https://scrapegraphai.com/blog/ai-agent-webscraping)  
3. Building Effective AI Agents \- Anthropic, truy cập vào tháng 5 9, 2026, [https://www.anthropic.com/research/building-effective-agents](https://www.anthropic.com/research/building-effective-agents)  
4. How to Build an AI Agent That Interacts With All Your Data Sources, truy cập vào tháng 5 9, 2026, [https://www.youtube.com/watch?v=LHKhYH0xDSg](https://www.youtube.com/watch?v=LHKhYH0xDSg)  
5. LLM Scraping in 2026: Firecrawl, Reader API, Crawl4AI, and Mobile Proxies — A Step-by-Step Guide, truy cập vào tháng 5 9, 2026, [https://mobileproxy.space/fr/pages/llm-scraping-in-2026-firecrawl-reader-api-crawl4ai-and-mobile-proxies--a-step-by-step-guide.html](https://mobileproxy.space/fr/pages/llm-scraping-in-2026-firecrawl-reader-api-crawl4ai-and-mobile-proxies--a-step-by-step-guide.html)  
6. Best Jina AI Alternative \- Firecrawl, truy cập vào tháng 5 9, 2026, [https://www.firecrawl.dev/alternatives/firecrawl-vs-jina-ai](https://www.firecrawl.dev/alternatives/firecrawl-vs-jina-ai)  
7. 7 Best Jina Reader Alternatives for AI Web Scraping in 2026, truy cập vào tháng 5 9, 2026, [https://scrapegraphai.com/blog/jina-alternatives](https://scrapegraphai.com/blog/jina-alternatives)  
8. 7 Best Web Scraping Tools for AI Agents (2026 Review) | Fastio, truy cập vào tháng 5 9, 2026, [https://fast.io/resources/best-web-scraping-tools-ai-agents/](https://fast.io/resources/best-web-scraping-tools-ai-agents/)  
9. Jina AI vs. Firecrawl for web-LLM extraction, truy cập vào tháng 5 9, 2026, [https://blog.apify.com/jina-ai-vs-firecrawl/](https://blog.apify.com/jina-ai-vs-firecrawl/)  
10. How to optimize a website for AI crawlers & AI agents \- Search Engine Land, truy cập vào tháng 5 9, 2026, [https://searchengineland.com/guide/optimize-for-ai-crawlers](https://searchengineland.com/guide/optimize-for-ai-crawlers)  
11. Getting clean Json Outputs from LLM for automations \- Reddit, truy cập vào tháng 5 9, 2026, [https://www.reddit.com/r/automation/comments/1rh0mtp/getting\_clean\_json\_outputs\_from\_llm\_for/](https://www.reddit.com/r/automation/comments/1rh0mtp/getting_clean_json_outputs_from_llm_for/)  
12. Structured Output for LLMs in Production: From json.loads() to ..., truy cập vào tháng 5 9, 2026, [https://pub.towardsai.net/structured-output-for-llms-in-production-from-json-loads-to-validated-objects-84e14a2504d0](https://pub.towardsai.net/structured-output-for-llms-in-production-from-json-loads-to-validated-objects-84e14a2504d0)  
13. The guide to structured outputs and function calling with LLMs \- Agenta, truy cập vào tháng 5 9, 2026, [https://agenta.ai/blog/the-guide-to-structured-outputs-and-function-calling-with-llms](https://agenta.ai/blog/the-guide-to-structured-outputs-and-function-calling-with-llms)  
14. An Analysis Of Common Errors In Vietnamese-English Translation, truy cập vào tháng 5 9, 2026, [https://www.iosrjournals.org/iosr-jhss/papers/Vol.30-Issue5/Ser-6/J3005067479.pdf](https://www.iosrjournals.org/iosr-jhss/papers/Vol.30-Issue5/Ser-6/J3005067479.pdf)  
15. some vietnamese students' problems with english grammar: a preliminary study \- Hawaii Pacific University, truy cập vào tháng 5 9, 2026, [https://www.hpu.edu/research-publications/tesol-working-papers/2008-fall/6.2-05-Dao.pdf](https://www.hpu.edu/research-publications/tesol-working-papers/2008-fall/6.2-05-Dao.pdf)  
16. Mastering JSON Prompting for LLMs \- MachineLearningMastery.com, truy cập vào tháng 5 9, 2026, [https://machinelearningmastery.com/mastering-json-prompting-for-llms/](https://machinelearningmastery.com/mastering-json-prompting-for-llms/)  
17. How to Build PII Detection, truy cập vào tháng 5 9, 2026, [https://oneuptime.com/blog/post/2026-01-30-llmops-pii-detection/view](https://oneuptime.com/blog/post/2026-01-30-llmops-pii-detection/view)  
18. Why Your LLM Probably Has a PII Problem (And How to Fix It) \- DEV Community, truy cập vào tháng 5 9, 2026, [https://dev.to/coridev/why-your-llm-probably-has-a-pii-problem-and-how-to-fix-it-4j13](https://dev.to/coridev/why-your-llm-probably-has-a-pii-problem-and-how-to-fix-it-4j13)  
19. Local LLMs solve privacy, but PII scrubbing is killing our turnaround time. What's your stack?, truy cập vào tháng 5 9, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1sk4w6k/local\_llms\_solve\_privacy\_but\_pii\_scrubbing\_is/](https://www.reddit.com/r/LocalLLaMA/comments/1sk4w6k/local_llms_solve_privacy_but_pii_scrubbing_is/)  
20. PII Extraction for RAG: Building Secure Document Pipelines \- Sandipan Haldar, truy cập vào tháng 5 9, 2026, [https://sandipanhaldar.com/blog/pii-extraction-for-rag/](https://sandipanhaldar.com/blog/pii-extraction-for-rag/)  
21. All Public Voices Are Equal, But Are Some More Equal Than Others to LLMs? \- arXiv, truy cập vào tháng 5 9, 2026, [https://arxiv.org/html/2604.17247v1](https://arxiv.org/html/2604.17247v1)  
22. Rate limits | OpenAI API, truy cập vào tháng 5 9, 2026, [https://developers.openai.com/api/docs/guides/rate-limits](https://developers.openai.com/api/docs/guides/rate-limits)  
23. Retry Strategies | Pydantic Docs, truy cập vào tháng 5 9, 2026, [https://pydantic.dev/docs/ai/evals/how-to/retry-strategies/](https://pydantic.dev/docs/ai/evals/how-to/retry-strategies/)  
24. Retry strategy | Generative AI on Vertex AI \- Google Cloud Documentation, truy cập vào tháng 5 9, 2026, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/retry-strategy](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/retry-strategy)  
25. How to Handle AI Agent Failures with Dapr Resiliency \- OneUptime, truy cập vào tháng 5 9, 2026, [https://oneuptime.com/blog/post/2026-03-31-dapr-agents-resiliency/view](https://oneuptime.com/blog/post/2026-03-31-dapr-agents-resiliency/view)  
26. mem0ai \- Dify Marketplace, truy cập vào tháng 5 9, 2026, [https://marketplace.dify.ai/plugin/beersoccer/mem0ai?language=en-US\&theme=system](https://marketplace.dify.ai/plugin/beersoccer/mem0ai?language=en-US&theme=system)  
27. Short-Term Memory for AI Agents: What, Why, and How? \- Mem0, truy cập vào tháng 5 9, 2026, [https://mem0.ai/blog/short-term-memory-for-ai-agents](https://mem0.ai/blog/short-term-memory-for-ai-agents)  
28. Hologres:Build long-term memory for LLMs with Mem0 \- Alibaba Cloud, truy cập vào tháng 5 9, 2026, [https://www.alibabacloud.com/help/en/hologres/user-guide/build-long-term-memory-for-llms-with-hologres-mem0](https://www.alibabacloud.com/help/en/hologres/user-guide/build-long-term-memory-for-llms-with-hologres-mem0)  
29. Custom Instructions \- Mem0 Documentation, truy cập vào tháng 5 9, 2026, [https://docs.mem0.ai/open-source/features/custom-instructions](https://docs.mem0.ai/open-source/features/custom-instructions)  
30. How to Build License-Compliant Synthetic Data Pipelines for AI Model Distillation, truy cập vào tháng 5 9, 2026, [https://developer.nvidia.com/blog/how-to-build-license-compliant-synthetic-data-pipelines-for-ai-model-distillation/](https://developer.nvidia.com/blog/how-to-build-license-compliant-synthetic-data-pipelines-for-ai-model-distillation/)  
31. Evidently 0.7.11: open-source synthetic data generation for LLM systems, truy cập vào tháng 5 9, 2026, [https://www.evidentlyai.com/blog/synthetic-data-generator-python](https://www.evidentlyai.com/blog/synthetic-data-generator-python)  
32. Title: Moving beyond prompt engineering: Why I built a validation pipeline for synthetic data generation : r/LangChain \- Reddit, truy cập vào tháng 5 9, 2026, [https://www.reddit.com/r/LangChain/comments/1sm29wx/title\_moving\_beyond\_prompt\_engineering\_why\_i/](https://www.reddit.com/r/LangChain/comments/1sm29wx/title_moving_beyond_prompt_engineering_why_i/)  
33. Synthetic Conversation Dataset Using Large Language Models \- Preprints.org, truy cập vào tháng 5 9, 2026, [https://www.preprints.org/manuscript/202510.2025](https://www.preprints.org/manuscript/202510.2025)  
34. An investigation into common errors in Vietnamese-English translation made by college freshmen: A case study at Foreign Trade University, truy cập vào tháng 5 9, 2026, [https://tdmujournal.vn/uploads/paper/files/6-Dang-Thi-My-Dung.pdf](https://tdmujournal.vn/uploads/paper/files/6-Dang-Thi-My-Dung.pdf)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAWCAYAAAD5Jg1dAAAAvElEQVR4Xt3RMQtBURjG8degKCWTmYFsSlaTlRQTvoeyynK/gLL5ECYDozJjt5hsLBb+p/Oe2+F0PwBP/brd5z73DveI/FayGGKJCNXPxzZ5bDBDDnWc0PdHJhMcUPC6Ec4ousI8NKOVKzRN3NF1RQ03CYcNPDD/LpKGcd/Byy80wTAokvoyrn6hccOpK8x/22GNjCtJG0+9xhnjgpLep8T+/L3Yw4iTxgJb9HR0FHtCQcxXKhigJfbl/8wb4ZAlMSoxI0oAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACYAAAAYCAYAAACWTY9zAAAB4klEQVR4Xu2WTShEURiGP6HkJ6RILIaiLERJNkrJQoqklJKVEimF/GSplBLlr5BIsiC/pVihLEk2slKypCzESuF9+87tXsOMO42Z2cxbT+ee79w7553zfefcKxJVVOFRNbgDDy6p0cdCqxgwBzaBx/SpZfABak0/FlSBe1BuYiFVFtgCmY5YOrgQNZHjiCeDdZDriIVMTEuvV6wEvIBtEOeI0/AMSHHEQqZmUOgVawWfYMgrngE6xE532MX6egeV3gORlK/6irjKwJv8rK//EDfNpGkDlq/6+g9xU52DItNnrXaL7na/4o2rEr764lG1IC6M+auvBDAAlsA4GHRcl4Jpgwc0gimwCLpAvNjP74JikA9OwJPoYrSLH/1VX4xxjOnm6m6AJjPGs7ACJIEj0GfumRV7Up5/h6LzUGz3xceK8Qy7As+itWXxCm7F/hFLLaJvCp5pp2BF1Ey/6KpYYprqRc1b9UoDNOLKWKDKA5eiq9AGjkEDqDPjTNu8geZpyo2xAvk9S65lbZAzkC2aqj1RwxQnuzZj1BgYFU2/P2Odpg1KXCEaokm+a9fE/rep4ABMiBY+2xvQA0bAI9gR3ST8cOAGGBYtkaDFTyCmzLpOdIxZSpPvNedLfD4sHwVRRURfGHNfD7vmLM8AAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,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>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACEAAAAVCAYAAADID4fUAAAByUlEQVR4Xu2WzSuEURTGj1AjhBSJhZWdLCQbIVnYkEQpS6WUDRthI6V8FPlKSglJJLGy8R8o2chKyY6FhVjJx/N0zttc18w09M6sPPVr5j33nveeufe5947Iv/4VWy3gFtwnSaumhacMsAoOQKU9U5vgA7TZcyZoAnegzmKhqRQcghInVgQuRAcsd+J5YBdUOLFQxKkd9mI14BkcgSwnzuKWQb4TC0U9oMqL9YFPMOrFi8GARJcspaIf3kCD35AuxfNDWlULXuWnH6hp8A7avXjoiucHil7YkxQXwUG2JLEftiXFRSTjBxYxDpbAMWiU6G7pBAtgAwyCbItz982CGdFzplo0p8uevymRHwKxiDHRl+SAE9ABcsEZGLG2FdBvOTyRg1OWfTkOP3fECmWVl+BJ1AsBL+DGElz5y0HvuEXzBGY7vRP4ahI8is5QvejAzGGfbuvzK8Uq4hwUgjWDhxrjQRGcpWbRJXwQzWdOLPMnJRbBtaSCy48v44xdgTJr43aeEt1tE6IzRDGX/YfAvsRf9oSaB4ui682BWFSBcWrtNCU/r+07Z2cO9IJ1UWPST7yH+Pxn8UYlvrgsES/GX8u/Atx9/r0T+QIiv12oss4hZAAAAABJRU5ErkJggg==>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABkAAAAXCAYAAAD+4+QTAAABPUlEQVR4Xu2UvUvDUBRHr6hQoejgpBUsbg5OgqA4ujgIIg4FZxFcBBcnJ/EfcBQRHEQUZ3Fy6uBax04WCk5uOoj4ce770OSlaRvIIvbAocnN5f4ayH0iPf4CZayExQ4M4w4e4z6OxR9bpnEb7/ADz+KP2zKJNdzEAi5jHeeiTYqGrOICNqX7kAE8wWt37TnEWxyK1H7Q12xI9yFT+IR7QX0NX3E2qBuyhizhpyRDVvALN4K6IWuIH5YWEtYNWUN0SKthuYbsSuthuYakDUurG7KGLOK7JIf5EP3KEnQKGcFx7HP3JXzEI9/g2MJnsfuXwIecy+8gz6jYzX7DeVfTngO8F/sHlEG8wguJL6j53nXT9UjR11Rf8AFnXE8Rb8QeGXqUeHS41i/FHimnWMWJSE8u9Ivd7nX3q/c9/jvf0rBG4yraNTcAAAAASUVORK5CYII=>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACUAAAAYCAYAAAB9ejRwAAABsklEQVR4Xu2VTygFURTGj1AWlD8hUWRhRRRSUkoUW7JAsRBiZyHFxsLKSrIhkkQRZWPF4mUhIpZKiZTsLMRK4fs6d8x9oxfpzUyv3le/Zu65d6Yz5373jEhSSfmjFnALHv5Iqz7mn1LAItgGZWZMrYAP0G7GqaAZ3IN6E/NNhWAHFFixHHAumkCxFc8EG6DEivkibsW4J1YNXsAuSLPiTHYBZFkxX9QNKjyxPvAJJj3xPDAs7hYHKvrpHTR5J8JSLD+FqlrwJj/9FKpi+Sk00cBrkmB+GgT7oB/MgEPQBRpFm++quD0sH8yCOdGD45zwDrBsqBF9J+8nQIZZE6Xf/MRKboItkC7azx5Bp5mfEu1jFP8EN6LNuRIcibYUqhScgQYwBnpE/xjf4hdcgmdRLzm8gmvRRG2ti+u3InAsbnUY57wjJl4HhkR3gOsdscJMelTi0Pe8SUXMlbKTYjKsRpto0hGJTopVOwXzEmBS9rpycCJanSrRCnKO239g4v/WCHgCF6AXLIl6kFeOGb8TNS99xkoNgGnRQ7FnxlcGHiZ6lO9gxbIlALEiuRKH7UkqYfQFYhdgouHN5aUAAAAASUVORK5CYII=>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACIAAAAXCAYAAABu8J3cAAACLElEQVR4Xu2VO2hUQRSGz6JCJAaRSERQUBHEKoEIEtDKB4IYgg8QLVIICiG1RrQQQopYKqZIEyzExtZKixWbYBoLo4WICIKo2AgBGx//d8/M3dnduWZTBvaHD/aee2bOP+fOzJp11dXatFlcEvNiRuxqfl3ogLhrnkMuYzpRTRwW98ScOC02NGUEHRSvxU1zAxfEKzGQ5JwTb8WQ2CKmxTOxNcnJCRPXxQuxV/SLR+aL2ZTkFcXemJtgUK94LlbEcMjZLd6Ly+EZbRNLYjKJ5cQcX8WRJLZPfBKnkpjdED/MuxJ1TExZo/UYSI0hTLOyunmHqsRnpujOJNYnXooF83mKti6ar4yWAR1q/X5821Yj6KH4Yr7CnHrEU2s3gvG6eV06W3SBbmDmgbgl7otl870QRcEqI7l4VCxYZaSMMwET/RFnQxKtmhXvzDduHJQruJoRilCsYyN0YHuZZnZG/BXXLL95o1YzskN8sA6MDIqfIZhuuGiEQqiqYFU8qq1gVTw6Jvg/I+z8XEHef7b85Yc2iidWbYSTwwkqEh9bsnuD0k+DRsVvcbzMaJwI4DfitO1JnlHuemAbsB04jaVOiO/WWG3Nmjcr4lhz094Jz2i/eTcuJrEr5gtgcSwS5fKOim9iJIkV1+xt8VFcNT++DDyUJoVncriuz5t3EcPpNU0nf4UcFhTFiYzzj5v/VUy05JTiGh8TJ81PSk7EeU8e+WsRXcUo8Lurrtaf/gGrgn+5KQsmmwAAAABJRU5ErkJggg==>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEQAAAAXCAYAAACyCenrAAADUklEQVR4Xu2XW6hOQRTHl1wiyp2Uco4HUooIL24PKA9eUEihlCTJC0rxIg9e3KOUJEkukSLCwymFeJAiColIkpRQyOX/O2vm2/ubs8/x4Tuhs//169t7ZvbMmjVrzcxnVqpUqVKl/pq6i+WiT1oRNFuMTQv/QdXNzgHivBiSVgTtFnPSwn9QdbNzirhnxQ7pL25anQZqR9VkZ2cxXqwS68MzZXk1iFvihRhj7pReoa6H2C6+iyWhjoE7hXrEM99tEktDG8Q4g8Ro81Cmr8HmBk8VXUO7nmJWoHcoQ6QxfU0Xk8z7GyXmixFWbUMtdja/7BTPxETzzs6KC5YN3CB2iSfikzgqDphPAIPWiUvmA/FLHWXUISZzSJwx7x9jXom55vvRCfFVPBfbxBaxUFwTV8QicSSUHRavzZ2LWLy75mMzhyaxRqwI7yfN51GLnc3qIo6Jd5YNwmq9FRtioyCMeWrFKcOKMlBRKNIPk20M7yzCXnHHfIXQRvPvV4d3hMMow2ExUoaLl1ZtG5HaJG6bR1sUKc4CsuAxCtqysyI8lD85mDATxwF5/Y5D2IjZd9iM8yvBZD+YrzBigm/MIygq9knbqGhbkUMgpjEiRS6aOxBHotbsrBJ5N0/cEA/EKXPP1sMhTJiJk26EaB7SsCG0Y4Jp30V9/opDEDZ/EZPDe1GfVaIDQpJ8mxDKaokQvM8mRsqhdKBxop/5irPyODm2LVJ7OuSjZXNL+4x2VjRDfLPq3M07hHpAeYcA79GAdKA95tERw5YTqm+oi2LPGhie28MhbKZE/X3zkwulfUY7K4oOyQ8w03zXZ8KLLft4q2X5CDssW3VCktCkPWWkQ2Oooz/qllm2ubGZ7gu/iE2VjXdoeEep8Sg6hMtVVHTIY8tSEC0wn8fKXFlbdjaL3ZujjrDiiOLE2WzuoM/iqmVGDjM/4q6Lc+bHdBT97De/p5wWa636fJ8mHpr3d1BcNr8+cypwUWLiwJgchcfNJ0MZv7xT/j7Xlu/4PjrkkXk0spDYR6rilLwdP7OzonjByYdcN2vZOF6kqs7unDitWvuvQ19EBN+nF78/UZoyjE+KxKO6SG3Z+d8rdUiHFpE60vxSBjy3Fr0dQuxD6f2mLn/tS5VqqR9ivtjwNGyd8gAAAABJRU5ErkJggg==>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHUAAAAXCAYAAAA1OADtAAAFL0lEQVR4Xu2ZW6iVRRTH/1JCUdHNbli4KwpCLCFURFMfupJFBZFQVNhDEIlYaRD0ECJYoGVUVhTVQ3SlHkro9rBFSClfgiTRIgsviFQoJWp0WT/WrPZ847fP2fuIsI99f/jznW++mTVr1lqzZs0+UoMGDRo0+J/jBOPZxuPKDw1GH3Dkt8Z/jD8Zz6t+Hhhcbnw7PQPnp7b5xjFZewO5QZ7UYDv1FXng8QzclNraxpOzdrLOfcbTsrYck403lI3HIh7VYDv1YrmO7M7AScbFxhlZGxhnXKPua7lfLuuYx6A7tR9cZdyk+rWMNb6ro+xUUsQEeSohCi81XiuPwsCZxluNTxhvT+85chnj5elnTnov+wZo5ztznaruTqVwutL4kPEuVeVhoHOMU+Xz8d4y3iIfE0VXzEUfdOsXpFZsg67TUls59/GpvWX82rjDeIV8PZGa0Weh8S/j0vStLA45ihj3uPGe1CfaWcclxhvl2YA1zpLrUsEi42752fCW8SW5Qh8ZTzRONO6Rn3lMcHfqfxuDE5Dxm1zGMuNrxnnGZ42/yhceQLkH5TJwFP04p37Q4U491/ipcbk8aOYYv5HrgJyWca183g3GF+Uy+Y485GLE5+TzfCYfn6fQXjDXuFk+zxuprWX8WO6gttxxtK0y/mg8aHzT+LI65yfn7IfGv40b0zfWFmcvGwnb0ecyVW1NMD5l/N243/iOcXX6+xnVFGp4/A+5MKLhPeMKefRNlysYBQKDMdI2+a4MTJFP8Ik8GADG2y53buAO4z55igogsyyUkEFgkarySGQcAXRNemcsxsNQ10cnw2NyJ7AjYsEzjX/Kd22/OF2+A8OpIOZuq1oo0acM0EDYui790oa9LkzvYWsCMTJUFGfY6wJ5UC9I3yoYaiIEn6GqYelHf8YFQgZFQIBFsbgwBAtvy42DkXKU6fdquaNyeSBkvq9OykM+ZxgpKYA8goxgC4SOI3Fq6J47FfBO+5E6Fd1ZAwVWfkSwS3Nbh1OHXUO3iQLsuOflKe0Leero5tR8stKp8d5W1QigdCpptE75kIEunGmgzrBDBV4psxccbadGO6mbtJyTlN5K/fp2al3H6+R5fKU6abVXgx2JU9mhKH/nfz0cISPf7XWG7VXHXjFSp2KzaepkldKpnJ0cYzx/UTUD1QHdy3XVottiSQNrjN+psytAGIzK6xH5AV8no3RqyNukaqoEpVOny89yzsYcFxl3yc+aMamtzrCD4lTIe3wvncoTfXA+9Ujd0UQ1fFb6u2+nkvJyhBO2qVMURQFDf4qVp+UKT5GfYXlVXDoVMOaAvGAKcGavkzsLpwGidbXxK1WvMVxrqAipygGOpVhh/CnRSUM7tTyne0E/TuUGEGuB2Ch2XwQlfQBBSwADbEMhd686AcvaX0hPEOk3KupakFYPyTvCnfIiJcBPWt/Lf58lv39gvFlekXFdWSBXmtI+ZFA9L5an7WjbYpwkV3auvMqjH0YhSHjSDzkPyEEALZHv7FflV4j18rs0QB5na8zBfDidPtHG2lhjuU7mzu/iw6F0KnOzppCHHrSBCXJ7oQc6l1e6h4175al2hapF6GzjVnmQsubP5T5AV64xYWeezBFz9g0UIVLyizLPwy69fYDxyIs7GkYrL+IB5iH9d/stdSRAFnfEsigpGTuidOpwiPV1+7EDedg0dmSOOns36AFh9Dj36khG+lK+UwgqdmN+524wChHXKn4J4kePn1VNpQ1GISjgXpfvVu7n5X9jGjRo0GCE+BcX0GBWJE5BTQAAAABJRU5ErkJggg==>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABkAAAAXCAYAAAD+4+QTAAABfklEQVR4Xu2UPyhHURTHj1CUSAb5U2IgmxKlZLL8BhImrDIqi1ImWYwWJSmTyErKwGBQJgPKJIvJxoDC9/vOPa/77q/762VSfp/69N4777xz3u/9zr0iZf4ytXAGbsMN2JO9XZJ6uCj67Cpsyd5WGuAZXIN1sA/ewSk/KUIHvIHzsAYW4AMc9JPIMryGjV5sFt7DZi8WUgV34JE7N9bhqejXSWBhNtizgGMAvsLxIO7TBZ9FX9JnEr7Bfgv0whcpbsIEJvKtYozCLyluMga/Rb9GghWLNQnjPlYs1iSNWyAslqcJi+Rqwmn4bZMlydkkViwW9ykqFovbhITFrMlKEPcZhp8Sb8IpS+Diu4DHoovJ4OR8uKPBRdsKK9x1G3yEm5bgWBCdWE5uyhx8gp3umkW4+q9EC5Mm0ZX9DodK5FXDQ7gv2QWa3NiC53BC9MFb0e3F4C8+Ed0yuJUYLM74gegQ7cJL2O7lpPCtuuE0HBFtnJdK0f+Qz/LI6zL/nR/WhVWYWmTGewAAAABJRU5ErkJggg==>

[image11]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABEAAAAUCAYAAABroNZJAAAAfklEQVR4XmNgGAWjAANwAHEaEPOgS5ACGIG4FYiN0SVIBSADeoGYBV2CFAByTQEQx0HZYCAAxJIkYjkgng/Ek4GYgRuIq4F4Fhl4BxB/ZaAAmADxaiCWQZcgFggD8WIglkeXIAVkAXEEuiApAJTYpgKxNLoEKQAUpbxQepABANsjErIyFZ/6AAAAAElFTkSuQmCC>