# Code Flow Guide For `src/data_pipeline`

File này dùng để đọc code theo luồng chạy. Cách đọc khuyến nghị:

1. Đọc `docs/project requirements/PRD_v2.md` để hiểu sản phẩm cần gì.
2. Đọc `docs/data layer/scraping/data_planning.md` để hiểu data pipeline chỉ chuẩn bị **static evaluation/benchmark/seed data**, không phải runtime learner memory.
3. Mở `src/data_pipeline/command_line_interface.py`, chọn command muốn hiểu, rồi đi theo các dòng được ghi bên dưới.

Ghi chú: số dòng là mốc đọc hiện tại. Nếu file được sửa sau này, hãy tìm tên function tương ứng.

## 0. Ý Nghĩa Của Thư Mục

`data_pipeline` không chạy gia sư AI production.

Nó tạo và kiểm tra các dataset tĩnh trong `data/processed/`:

- V-English Error Bank
- Industry Context Library
- IELTS Writing Samples
- Pedagogical Prompt Samples
- Mood Pattern Samples
- Mem0 Initial Facts

Các dataset này dùng cho benchmark, regression test, demo seed, và quality gate alpha. Runtime personalization vẫn nằm ở backend runtime services.

## 1. Điểm Vào Chung

### `command_line_interface.py`

`command_line_interface.py:186`

```python
def build_parser() -> argparse.ArgumentParser:
```

Đây là nơi định nghĩa toàn bộ lệnh CLI. Nếu muốn biết pipeline có những luồng nào, bắt đầu ở function này.

`command_line_interface.py:191`

```python
sc = sub.add_parser("scrape", help="Run keyless collectors")
```

Tạo command `scrape`. Command này ứng với bước 1 trong `data_planning.md`: chuẩn bị nguồn tham chiếu nhỏ, hợp lệ, có provenance.

`command_line_interface.py:207`

```python
ex = sub.add_parser("extract", help="Rule-based extractors (no LLM)")
```

Tạo command `extract`. Command này chuyển raw reference data thành processed candidate datasets mà không gọi LLM.

`command_line_interface.py:223`

```python
va = sub.add_parser("validate", help="Validate processed datasets")
```

Tạo command `validate`. Command này kiểm tra dữ liệu processed có đúng schema Pydantic hay không.

`command_line_interface.py:226`

```python
gen = sub.add_parser("generate", ...)
```

Tạo command `generate`. Command này dùng LLM để tạo static seed/eval data khi dữ liệu local chưa đủ.

`command_line_interface.py:236`

```python
proc = sub.add_parser("process-existing", ...)
```

Tạo command `process-existing`. Đây là luồng local-only: không scrape, không LLM, chỉ làm sạch/mở rộng data đã có.

`command_line_interface.py:248`

```python
qp = sub.add_parser("quality-process", ...)
```

Tạo command `quality-process`. Đây là quality gate cuối trên dữ liệu processed.

`command_line_interface.py:259`

```python
au = sub.add_parser("audit", ...)
```

Tạo command `audit`. Command này so dataset hiện tại với yêu cầu PRD/data planning.

`command_line_interface.py:271`

```python
def main(argv: Iterable[str] | None = None) -> int:
```

Đây là entrypoint thực sự khi chạy `python -m data_pipeline ...`.

`command_line_interface.py:272`

```python
parser = build_parser()
```

Tạo parser chứa các command ở trên.

`command_line_interface.py:273`

```python
args = parser.parse_args(argv)
```

Đọc command người dùng nhập.

`command_line_interface.py:275`

```python
return args.func(args)
```

Gọi function xử lý command. Đây là dòng chuyển từ CLI sang từng phase.

## 2. Luồng `info`

Chạy:

```bash
python -m data_pipeline info
```

### `command_line_interface.py`

`command_line_interface.py:148`

```python
def cmd_info(_args: argparse.Namespace) -> int:
```

Function này không thay đổi dữ liệu. Nó chỉ giúp người mới thấy pipeline đang phục vụ mục tiêu gì và hiện có bao nhiêu file raw/processed.

`command_line_interface.py:149-154`

```python
print("a20-data-pipeline")
print("  purpose: prepare static evaluation/benchmark/seed datasets")
print("  phases:")
...
```

Các dòng này cố tình nhắc lại ranh giới trong `data_planning.md`: đây là static eval/seed pipeline, không phải runtime tutor.

`command_line_interface.py:156-157`

```python
raw = Path("data/raw")
proc = Path("data/processed")
```

Trỏ tới hai vùng dữ liệu chính:

- `data/raw`: dữ liệu tham chiếu thu thập được.
- `data/processed`: dữ liệu đã chuẩn hóa để validate/audit/seed/demo.

`command_line_interface.py:158-178`

Vòng lặp ở đoạn này in danh sách file và số entry. Mục đích là giúp kiểm tra nhanh pipeline đang có gì trước khi chạy các bước khác.

## 3. Luồng `scrape`: Thu Thập Nguồn Tham Chiếu

Chạy:

```bash
python -m data_pipeline scrape --sources wikipedia huggingface
```

### `command_line_interface.py`

`command_line_interface.py:38`

```python
def cmd_scrape(args: argparse.Namespace) -> int:
```

Bắt đầu phase `reference_data_collection`.

`command_line_interface.py:39`

```python
from .reference_data_collection.sources import wikipedia, huggingface, ielts_public
```

Import ba collector. Mỗi collector tương ứng một nguồn reference trong `data_planning.md`.

`command_line_interface.py:41-44`

Comment ở đây giải thích vì sao IELTS không nằm trong default source: nhiều tài liệu IELTS có vấn đề bản quyền, nên alpha ưu tiên manual/synthetic seed.

`command_line_interface.py:45`

```python
selected = set(args.sources or ["wikipedia", "huggingface"])
```

Nếu user không chọn nguồn, pipeline chỉ lấy Wikipedia và HuggingFace/JFLEG. Đây là lựa chọn an toàn theo data planning: nhỏ, dễ kiểm chứng, hạn chế scraping rộng.

`command_line_interface.py:48-52`

```python
if "wikipedia" in selected:
    report["wikipedia"] = wikipedia.collect(...)
```

Gọi collector Wikipedia để lấy raw glossary theo ngành nghề. Output phục vụ **Industry Context Library**.

`command_line_interface.py:53-57`

```python
if "huggingface" in selected:
    report["huggingface"] = huggingface.collect(...)
```

Gọi collector HuggingFace/JFLEG. Output phục vụ **V-English Error Bank** thông qua rule-based extraction.

`command_line_interface.py:58-61`

```python
if "ielts" in selected:
    report["ielts"] = ielts_public.collect(...)
```

IELTS là opt-in. Chỉ chạy khi người dùng chủ động chọn `--sources ielts`.

`command_line_interface.py:63-67`

```python
summary_path = Path(args.out_dir) / "scrape_report.json"
...
print(json.dumps(report, ...))
```

Ghi provenance/report cho lần scrape. Đây là cách pipeline giữ dấu vết nguồn tham chiếu.

### `reference_data_collection/sources/wikipedia.py`

`wikipedia.py:27`

```python
API_URL = "https://en.wikipedia.org/w/api.php"
```

Wikipedia collector dùng MediaWiki API thay vì crawl HTML tùy tiện.

`wikipedia.py:106`

```python
_RETRY = RetryConfig(...)
```

Thiết lập retry vì collection là network I/O và có thể lỗi tạm thời.

`wikipedia.py:110`

```python
def _http_get(...):
```

Wrapper HTTP GET có retry, dùng cho MediaWiki API.

`wikipedia.py:116`

```python
def _fetch_wikitext(...):
```

Lấy wikitext raw từ một page cụ thể.

`wikipedia.py:137`

```python
def _strip_wikitext(text: str) -> str:
```

Làm sạch markup Wikipedia để downstream không học hoặc validate trên text nhiễu.

`wikipedia.py:148`

```python
def _extract_terms(wikitext: str) -> List[Dict[str, str]]:
```

Rút các cặp `term/definition`. Đây là nguyên liệu cho Industry Context Library.

`wikipedia.py:171`

```python
def collect(...):
```

Function được CLI gọi. Nó gom glossary theo industry và ghi vào `data/raw/wikipedia/glossaries/`.

### `reference_data_collection/sources/huggingface.py`

`huggingface.py:49`

```python
def _download(...):
```

Tải raw JFLEG data.

`huggingface.py:59`

```python
def _zip_jfleg(src: str, refs: List[str]) -> Iterable[Dict[str, object]]:
```

Ghép câu sai với các câu sửa. Đây là cặp dữ liệu cần cho extraction lỗi.

`huggingface.py:75`

```python
def collect_jfleg(...):
```

Collector JFLEG theo đường public/raw.

`huggingface.py:130`

```python
def collect(...):
```

Function được CLI gọi. Output chính là `data/raw/huggingface/jfleg/*.jsonl`.

## 4. Luồng `extract`: Raw Reference Data -> Processed Candidates

Chạy:

```bash
python -m data_pipeline extract
```

### `command_line_interface.py`

`command_line_interface.py:75`

```python
def cmd_extract(args: argparse.Namespace) -> int:
```

Bắt đầu phase extract. Phase này không gọi LLM.

`command_line_interface.py:82`

```python
selected = set(args.targets or ["jfleg", "wiki_vocab"])
```

Nếu user không chọn target, chạy cả JFLEG -> errors và Wiki -> industry vocab.

`command_line_interface.py:84-89`

```python
report["jfleg_to_errors"] = jfleg_to_errors.run(...)
```

Chuyển raw JFLEG thành candidate lỗi tiếng Anh. Output là `data/processed/common_errors/jfleg_auto_extracted.json`.

`command_line_interface.py:90-97`

```python
report["wiki_to_industry_vocab"] = wiki_to_industry_vocab.run(...)
```

Chuyển raw Wikipedia glossary thành candidate industry vocabulary. Có thể merge vào canonical library nếu truyền `--merge`.

`command_line_interface.py:98-102`

Ghi `extract_report.json` để biết lần extract đã làm gì.

### `raw_to_processed_extractors/jfleg_to_errors.py`

`jfleg_to_errors.py:55`

```python
def tokenize(s: str) -> List[str]:
```

Tách câu thành token để so sánh câu sai và câu sửa.

`jfleg_to_errors.py:67`

```python
def _best_correction(source: str, corrections: Iterable[str]) -> str | None:
```

JFLEG có nhiều correction. Dòng này chọn correction phù hợp nhất để tạo một error candidate ổn định.

`jfleg_to_errors.py:86`

```python
def _classify(span1: List[str], span2: List[str]) -> str | None:
```

Phân loại lỗi rule-based: article, preposition, tense, modal, word choice... Đây là cầu nối với Error DNA/error taxonomy trong PRD.

`jfleg_to_errors.py:137`

```python
def extract_from_pair(source: str, correction: str) -> List[ESLErrorInstance]:
```

Tạo một hoặc nhiều `ESLErrorInstance` từ cặp câu sai/sửa.

`jfleg_to_errors.py:183`

```python
def extract_from_jsonl(...):
```

Đọc raw JFLEG JSONL và áp dụng extraction cho từng dòng.

`jfleg_to_errors.py:201`

```python
def run(...):
```

Function được CLI gọi. Nó ghi processed candidate file và report metadata.

### `raw_to_processed_extractors/wiki_to_industry_vocab.py`

`wiki_to_industry_vocab.py:37`

```python
def _guess_cefr(term: str, definition_en: str) -> str:
```

Gán CEFR sơ bộ cho từ vựng ngành. CEFR là một phần user profile/onboarding trong PRD.

`wiki_to_industry_vocab.py:50`

```python
def _to_vocab_item(term: str, definition_en: str, industry: str) -> dict:
```

Chuẩn hóa raw term thành schema item của Industry Context Library.

`wiki_to_industry_vocab.py:70`

```python
def _load_raw(raw_dir: Path) -> Dict[str, List[dict]]:
```

Đọc raw glossary đã scrape.

`wiki_to_industry_vocab.py:83`

```python
def run(...):
```

Function được CLI gọi. Nó tạo `wiki_auto_extracted.json` và có thể merge vào canonical `industry_context_library.json`.

## 5. Luồng `generate`: Tạo Synthetic Static Seed/Eval Data

Chạy ví dụ:

```bash
python -m data_pipeline generate --task mood --count 60
```

### `command_line_interface.py`

`command_line_interface.py:114`

```python
def cmd_generate(args: argparse.Namespace) -> int:
```

Entrypoint cho LLM-backed synthetic generation.

`command_line_interface.py:115`

```python
from .evaluation_seed_preparation.generate_synthetic_seed_datasets import run as _generate_run
```

Chuyển từ CLI sang module tạo synthetic datasets.

`command_line_interface.py:117`

```python
return _generate_run(args)
```

Chạy task được chọn.

### `generate_synthetic_seed_datasets.py`

`generate_synthetic_seed_datasets.py:74`

```python
def make_llm() -> StructuredLLM:
```

Tạo LLM client có structured output. Mục đích: synthetic data vẫn phải trả JSON đúng schema, không phải text tự do.

`generate_synthetic_seed_datasets.py:123`

```python
def run_errors(count: int) -> None:
```

Sinh thêm V-English Error Bank records khi seed hiện tại chưa đủ.

`generate_synthetic_seed_datasets.py:144`

```python
def builder(sampled: list[dict]) -> str:
```

Tạo prompt dựa trên seed hiện có để giảm trùng lặp và giữ domain Vietnamese-English ESL.

`generate_synthetic_seed_datasets.py:194`

```python
def run_industry(count_per_industry: int, only_industry: str | None) -> None:
```

Sinh thêm industry vocabulary theo ngành. Phục vụ Context Injection/industry-specific content benchmark.

`generate_synthetic_seed_datasets.py:266`

```python
def run_mem0(count_per_persona: int, only_persona: str | None) -> None:
```

Sinh static Mem0 Initial Facts cho demo/retrieval benchmark. Không phải production learner memory.

`generate_synthetic_seed_datasets.py:350`

```python
def run_ielts(count: int) -> None:
```

Sinh IELTS Writing Samples để test feedback/calibration.

`generate_synthetic_seed_datasets.py:418`

```python
def run_pedagogical(count: int) -> None:
```

Sinh Pedagogical Prompt Samples để test scaffolding/Socratic style.

`generate_synthetic_seed_datasets.py:489`

```python
def run_mood(count: int) -> None:
```

Sinh Mood Pattern Samples để test Mood-Adaptive Session routing.

`generate_synthetic_seed_datasets.py:550`

```python
TASKS: dict[str, Callable[[argparse.Namespace], None]] = {...}
```

Map tên task CLI sang function xử lý.

`generate_synthetic_seed_datasets.py:580`

```python
def run(args: argparse.Namespace) -> int:
```

Chọn task cần chạy. Nếu `--task all`, chạy toàn bộ synthetic generation tasks.

### `synthetic_generation_workflow.py`

`synthetic_generation_workflow.py:56`

```python
class SyntheticPipeline(Generic[T]):
```

Workflow dùng chung cho synthetic generation.

`synthetic_generation_workflow.py:83`

```python
def expand(self, system_prompt: str, user_prompt: str) -> Sequence[BaseModel]:
```

Gọi LLM để sinh candidate records.

`synthetic_generation_workflow.py:88`

```python
def judge(self, candidate_json: str, rubric: str) -> JudgeVerdict:
```

LLM-as-judge kiểm tra candidate theo rubric.

`synthetic_generation_workflow.py:104`

```python
def decontaminate(...)
```

Loại candidate trùng với seed hoặc trùng với candidate đã accept.

`synthetic_generation_workflow.py:129`

```python
def run(...)
```

Ghép các bước: sample seed -> expand -> decontaminate -> judge -> accept.

### `scrub_pii.py`

`scrub_pii.py:62`

```python
class PIISentinel:
```

Bộ lọc PII cho seed/eval data. Lý do tồn tại: PRD có yêu cầu privacy và delete-my-data; seed/eval data không được vô tình chứa PII.

`scrub_pii.py:87`

```python
def scrub(self, text: str) -> str:
```

Điểm vào chính để scrub text trước khi lưu.

`scrub_pii.py:114-151`

Các `_scrub_*` functions xử lý email, phone, long digits, names, Presidio fallback.

## 6. Luồng `process-existing`: Local-Only Cleanup Và Expansion

Chạy:

```bash
python -m data_pipeline process-existing
```

### `command_line_interface.py`

`command_line_interface.py:120`

```python
def cmd_process_existing(args: argparse.Namespace) -> int:
```

Bắt đầu luồng local-only. Không scrape, không LLM.

`command_line_interface.py:122`

```python
from .evaluation_seed_preparation.process_existing_seed_data import run_all
```

Import module xử lý data có sẵn.

`command_line_interface.py:124`

```python
run_all(args)
```

Chạy tất cả bước cleanup/expansion deterministic.

### `process_existing_seed_data.py`

`process_existing_seed_data.py:61`

```python
def clean_wiki_text(value: str) -> str:
```

Xóa raw wiki markup, URL, HTML tag. Mục đích: Industry Context Library không chứa text nhiễu.

`process_existing_seed_data.py:78`

```python
def clean_industry_vocab() -> dict[str, int]:
```

Áp dụng cleanup cho canonical và auto-extracted industry vocab.

`process_existing_seed_data.py:160`

```python
def promote_jfleg_candidates(...)
```

Promote rule-filtered JFLEG candidates vào Error Bank cho đủ target alpha, nhưng vẫn gắn metadata review.

`process_existing_seed_data.py:237`

```python
def expand_ielts(target: int = 60) -> dict[str, int]:
```

Mở rộng IELTS samples bằng template local để đạt size target mà không gọi LLM.

`process_existing_seed_data.py:300`

```python
def expand_pedagogical(target: int = 80) -> dict[str, int]:
```

Mở rộng Pedagogical Prompt Samples theo scenario và scaffolding steps.

`process_existing_seed_data.py:349`

```python
def expand_mood(target: int = 60) -> dict[str, int]:
```

Mở rộng Mood Pattern Samples theo 5 energy levels trong PRD creative feature.

`process_existing_seed_data.py:395`

```python
def expand_mem0(target_per_persona: int = 100) -> dict[str, int]:
```

Mở rộng Mem0 Initial Facts cho persona seed. Đây là demo/retrieval seed, không phải runtime Mem0.

`process_existing_seed_data.py:446`

```python
def run_all(args: argparse.Namespace) -> dict[str, Any]:
```

Chạy toàn bộ local-only steps và ghi `offline_process_report.json`.

## 7. Luồng `quality-process`: Alpha Quality Gate

Chạy:

```bash
python -m data_pipeline quality-process --no-llm
```

### `command_line_interface.py`

`command_line_interface.py:128`

```python
def cmd_quality_process(args: argparse.Namespace) -> int:
```

Bắt đầu quality gate.

`command_line_interface.py:130`

```python
from .evaluation_seed_preparation.run_alpha_quality_gate import run_all
```

Import quality gate module.

`command_line_interface.py:132`

```python
run_all(args)
```

Chạy quality checks và ghi report.

### `run_alpha_quality_gate.py`

`run_alpha_quality_gate.py:26-28`

```python
REVIEW_TAG = "needs_teacher_review"
QUALITY_TAG = "alpha_quality_reviewed"
OFFLINE_TAG = "offline_expanded"
```

Các tag này ghi trạng thái review vào processed records.

`run_alpha_quality_gate.py:33`

```python
class LLMQualityCertification(BaseModel):
```

Schema cho optional aggregate LLM certification. Lưu ý: certification này chỉ đọc aggregate metrics, không gửi raw rows.

`run_alpha_quality_gate.py:71`

```python
def quality_review_errors() -> dict[str, Any]:
```

Review Error Bank: clear review tag khi đạt gate, nâng confidence, recategorize một số case lexical.

`run_alpha_quality_gate.py:172`

```python
def quality_review_industry() -> dict[str, Any]:
```

Đảm bảo industry vocab có đủ `definition_vi`, `example_sentence`, `usage_note`.

`run_alpha_quality_gate.py:244`

```python
def quality_review_ielts() -> dict[str, Any]:
```

Đảm bảo IELTS essay đủ tối thiểu 250 words và không còn placeholder.

`run_alpha_quality_gate.py:277`

```python
def _review_collection(path: Path, list_key: str, id_prefix: str) -> dict[str, Any]:
```

Helper dùng cho pedagogical/mood collections: đánh dấu review và decontamination.

`run_alpha_quality_gate.py:299`

```python
def quality_review_mem0() -> dict[str, Any]:
```

Deduplicate Mem0 seed facts và đánh dấu quality reviewed.

`run_alpha_quality_gate.py:329`

```python
def llm_certify(report_checks: dict[str, Any]) -> dict[str, Any]:
```

Optional LLM review trên aggregate report. Không dùng để thay schema validation.

`run_alpha_quality_gate.py:374`

```python
def run_all(args: argparse.Namespace | None = None) -> dict[str, Any]:
```

Chạy toàn bộ quality gate và ghi `quality_process_report.json`.

## 8. Luồng `validate`: Schema Validation

Chạy:

```bash
python -m data_pipeline validate
```

### `command_line_interface.py`

`command_line_interface.py:106`

```python
def cmd_validate(args: argparse.Namespace) -> int:
```

Chuyển sang readiness check schema.

`command_line_interface.py:111`

```python
return _validate_main()
```

Chạy validator.

### `validate_processed_dataset_schemas.py`

`validate_processed_dataset_schemas.py:41`

```python
def _check(items: Iterable[dict], schema: type[BaseModel], label: str) -> tuple[int, int]:
```

Validate từng item bằng schema Pydantic.

`validate_processed_dataset_schemas.py:53`

```python
def _check_dedup(items: Iterable[dict], key: str, label: str) -> int:
```

Kiểm tra trùng key ở những dataset cần uniqueness.

`validate_processed_dataset_schemas.py:66`

```python
def main() -> int:
```

Đọc tất cả processed datasets và validate từng loại: errors, industry vocab, Mem0, IELTS, pedagogical, mood, auto-extracted candidates, learner profiles.

### `processed_dataset_schemas.py`

`processed_dataset_schemas.py:22`

```python
class ErrorCategory(str, Enum):
```

Danh mục lỗi dùng cho Error Bank và Error DNA mapping.

`processed_dataset_schemas.py:50`

```python
CEFR_PATTERN = r"^(A1|A2|B1|B2|C1|C2)$"
```

Ràng buộc CEFR theo onboarding PRD.

`processed_dataset_schemas.py:53`

```python
class ESLErrorInstance(BaseModel):
```

Schema một lỗi ESL trong V-English Error Bank.

`processed_dataset_schemas.py:107`

```python
class IndustryVocabItem(BaseModel):
```

Schema một thuật ngữ ngành cho Industry Context Library.

`processed_dataset_schemas.py:145`

```python
class Mem0Fact(BaseModel):
```

Schema fact tĩnh cho Mem0 Initial Facts seed/demo.

`processed_dataset_schemas.py:174`

```python
class IELTSWritingSample(BaseModel):
```

Schema IELTS Writing Sample.

`processed_dataset_schemas.py:198`

```python
class PedagogicalPrompt(BaseModel):
```

Schema tình huống scaffolding/Socratic prompt.

`processed_dataset_schemas.py:227`

```python
class MoodPatternSample(BaseModel):
```

Schema mood sample cho Mood-Adaptive Session testing.

`processed_dataset_schemas.py:263`

```python
class LearnerProfile(BaseModel):
```

Schema persona dùng để sinh synthetic dialogue/eval data.

## 9. Luồng `audit`: PRD/Data Planning Readiness

Chạy:

```bash
python -m data_pipeline audit
```

### `command_line_interface.py`

`command_line_interface.py:136`

```python
def cmd_audit(args: argparse.Namespace) -> int:
```

Chuyển sang PRD/data-planning audit.

`command_line_interface.py:141`

```python
return _audit_main(args)
```

Chạy audit.

### `audit_prd_eval_corpus_readiness.py`

`audit_prd_eval_corpus_readiness.py:29`

```python
CORE_INDUSTRIES = {"IT", "Marketing", "Sales", "Finance", "Education"}
```

Các ngành cốt lõi để kiểm tra Industry Context Library có đủ scope alpha không.

`audit_prd_eval_corpus_readiness.py:30`

```python
DOC_TARGETS = {...}
```

Target size của từng dataset theo data planning.

`audit_prd_eval_corpus_readiness.py:38`

```python
WIKI_MARKUP_RE = re.compile(...)
```

Pattern phát hiện raw wiki markup còn sót lại.

`audit_prd_eval_corpus_readiness.py:60`

```python
def audit() -> dict[str, Any]:
```

Chạy toàn bộ checks: raw reports, raw core industries, JFLEG count, Error Bank count, teacher review, IELTS length, pedagogical/mood/Mem0 counts, industry required fields, wiki cleanup, A1 curriculum warning.

`audit_prd_eval_corpus_readiness.py:176`

```python
def main(_args: argparse.Namespace | None = None) -> int:
```

In audit JSON và trả exit code. Nếu có fail thì exit 1, nếu chỉ warning thì vẫn pass-with-warnings.

## 10. Shared Support Files

### `shared_pipeline_support/data_file_paths.py`

`data_file_paths.py:7`

```python
ROOT = Path(__file__).resolve().parents[3]
```

Tìm project root từ vị trí file support. Các path khác dựa vào đây.

`data_file_paths.py:9-11`

```python
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
```

Định nghĩa hai vùng dữ liệu chính.

`data_file_paths.py:27-35`

Các biến như `ERROR_BANK`, `INDUSTRY_CANONICAL`, `IELTS`, `PEDAGOGICAL`, `MOOD`, `MEM0`, `LEARNER_PROFILES` là canonical file paths cho từng output trong `data_planning.md`.

`data_file_paths.py:41`

```python
GENERATED_DATASETS = {...}
```

Map task synthetic generation sang file output.

### `shared_pipeline_support/json_dataset_file_io.py`

`json_dataset_file_io.py:15`

```python
def load_json(path: Path) -> dict[str, Any]:
```

Đọc JSON UTF-8.

`json_dataset_file_io.py:19`

```python
def save_json(...)
```

Ghi JSON UTF-8 và tự tạo parent directory.

`json_dataset_file_io.py:30`

```python
def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
```

Đọc JFLEG/raw JSONL.

`json_dataset_file_io.py:39`

```python
def write_jsonl(...)
```

Ghi raw JFLEG rows.

### `shared_pipeline_support/structured_llm_client.py`

File này chỉ phục vụ synthetic generation và optional LLM certification. Nếu đọc luồng local-only, có thể bỏ qua.

`structured_llm_client.py:144`

```python
class StructuredLLM:
```

Client ép LLM trả về JSON hợp schema.

`structured_llm_client.py:174`

```python
def parse(...)
```

Gọi model, validate Pydantic, và repair một lần nếu output sai schema.

### `shared_pipeline_support/llm_call_observability.py`

File này ghi JSONL trace cho LLM calls: token, latency, cost estimate. Nó giúp admin/cost monitoring trong PRD nhưng không quyết định nội dung dataset.

## 11. Các Luồng Nên Chạy Khi Dev Local

Nếu chỉ muốn kiểm tra dataset hiện có:

```bash
python -m data_pipeline info
python -m data_pipeline validate
python -m data_pipeline audit
```

Nếu muốn làm sạch và chuẩn hóa lại local data:

```bash
python -m data_pipeline process-existing
python -m data_pipeline quality-process --no-llm
python -m data_pipeline validate
python -m data_pipeline audit
```

Nếu muốn thu thập lại nguồn tham chiếu nhỏ:

```bash
python -m data_pipeline scrape --sources wikipedia huggingface
python -m data_pipeline extract
python -m data_pipeline validate
python -m data_pipeline audit
```

Nếu muốn dùng LLM để mở rộng static seed/eval data:

```bash
python -m data_pipeline generate --task all
python -m data_pipeline quality-process
python -m data_pipeline validate
python -m data_pipeline audit
```

## 12. Cách Nhận Biết Code Thuộc Runtime Hay Static Pipeline

Nếu code đọc/ghi `data/raw` hoặc `data/processed`, nó thuộc static data pipeline.

Nếu code xử lý real user session, chat message, SM-2 review thật, Mem0 production fact, Error DNA thật, hoặc Context Injection runtime, nó không nên nằm trong thư mục này.

