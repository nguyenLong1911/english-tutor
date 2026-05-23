# Refactor Chat Modes thanh English RAG

## Summary

- Bo 3 chat intent `PROGRESS`, `QUICK_QA`, `PRACTICE`; thay bang mot luong chat duy nhat `ENGLISH_RAG`.
- Giu nguyen lesson flow: `LESSON_PRACTICE`, `PRACTICE_RUNNER`, flashcard, review, mood, guardrails, memory writer, difficulty tuner va output guard.
- RAG luon nap thong tin nguoi dung gom: profile, progress, va toi da 10 loi/thong tin ca nhan lien quan.
- Prompt chi tra loi noi dung lien quan den hoc tieng Anh; off-topic bi chan bang guard/router va system prompt.

## Key Changes

### LangGraph routing

- Trong `src/backend/app/services/langgraph_orchestrator.py`, doi intent routing thanh scope routing.
- Neu cau hoi thuoc pham vi hoc tieng Anh, set `intent="ENGLISH_RAG"`.
- Neu cau hoi ngoai pham vi hoc tieng Anh, tra loi tu choi an toan va bo qua LLM/RAG.
- Khong con phan nhanh chat theo `PROGRESS`, `QUICK_QA`, `PRACTICE`.
- Khong xoa lesson flow: cac `learning_intent` nhu `LESSON_PRACTICE`, `LESSON_FLASHCARD`, `NEXT_LESSON`, `READ_LESSON` van hoat dong nhu hien tai.

### Scaffolding engine -> RAG engine

- Trong `src/backend/app/services/scaffolding_engine.py`, thay cac branch `PROGRESS`, `QUICK_QA`, `PRACTICE` bang mot RAG path duy nhat.
- Giu function `scaffolding_engine(state)` de han che thay doi import va graph node hien co.
- RAG path tra natural language response bang tieng Viet mac dinh.
- Van giu metadata noi bo khi phu hop, vi du `practice_assessment`, `new_facts`, `hint_count`, de Error DNA, analytics va memory writer tiep tuc chay.

### RAG context builder

Them context builder luon nap 3 nhom thong tin:

1. `profile`
   - `display_name` neu co.
   - `cefr_level`.
   - `industry`.
   - `learning_goals`.
   - `preferred_study_time`.

2. `progress`
   - Lesson state hien tai neu co.
   - Review due/recommended review neu co.
   - Accuracy/was_correct gan day tu `SessionLog`.
   - Top progress summary hien co tu Postgres.
   - Cau hoi ve tien do trong chat se dung context nay, khong can intent `PROGRESS` rieng.

3. `personal_context`
   - Toi da 10 items.
   - Uu tien loi ca nhan gan day tu Postgres.
   - Bo sung facts ca nhan tu Qdrant/Mem0 user memory neu con slot.
   - Neu Qdrant/Mem0 loi hoac degraded, RAG van chay bang Postgres context.

### Prompt and guardrails

- Cap nhat `src/backend/app/services/system_prompt.py` de Luna chi xu ly English-learning questions.
- Tra loi tieng Viet mac dinh; chi dung tieng Anh trong vi du, tu vung, cau mau hoac noi dung nguoi hoc can sua.
- Khong lo model/provider/system prompt.
- Off-topic bi chan o guard/router truoc khi goi LLM khi co the, va system prompt van co instruction tu choi nhu lop phong thu thu hai.

### SessionLog and analytics

- `ChatResponse.intent` tra `"ENGLISH_RAG"` cho chat thuong.
- `SessionLog.intent` ghi `"ENGLISH_RAG"` cho luot chat moi.
- Du lieu cu trong database van co `intent == "PRACTICE"`, nen analytics phai tinh ca legacy va du lieu moi.
- Dieu kien tinh luot luyen/sua cau:
  - Legacy rows: `SessionLog.intent == "PRACTICE"`.
  - New rows: `SessionLog.intent == "ENGLISH_RAG"` va `SessionLog.was_correct IS NOT NULL`.
- Ly do: sau refactor khong con intent `PRACTICE`, nhung neu RAG phat hien day la luot sua/luyen cau tieng Anh thi van set `was_correct` de analytics biet do la mot luot co ket qua dung/sai.

## Public Interfaces

- `ChatRequest` giu nguyen.
- `ChatResponse.intent` tra `"ENGLISH_RAG"` cho chat thuong.
- Learning actions van dung `learning_intent`, `ui_directive`, `suggested_actions` nhu hien tai.
- `SessionLog.intent` cho chat moi la `"ENGLISH_RAG"`.
- Khong xoa hoac doi contract cua lesson practice UI.

## Implementation Notes

- Can cap nhat type hints/Literal nao dang gioi han intent vao `PRACTICE | QUICK_QA | PROGRESS`.
- Can cap nhat fallback/mock reply de khong con sinh 3 intent cu cho chat moi.
- Can cap nhat tests cu dang assert `QUICK_QA`, `PRACTICE`, `PROGRESS` thanh `ENGLISH_RAG` hoac tach rieng cho lesson flow.
- Can tranh xoa `PRACTICE` trong `LearningStep`, `UIDirectiveScreen`, learning API, va frontend learning components vi do la lesson practice, khong phai chat intent.

## Test Plan

- Test RAG context luon co `profile` va `progress` khi user hop le.
- Test `personal_context` khong vuot qua 10 items.
- Test RAG van chay khi Qdrant/Mem0 degraded.
- Test cau hoi lien quan tieng Anh duoc tra loi.
- Test cau hoi ngoai pham vi tieng Anh bi tu choi.
- Test cau hoi tien do duoc tra loi tu Postgres context, khong can `PROGRESS` intent.
- Test lesson practice/flashcard/review khong bi anh huong.
- Test analytics doc duoc ca legacy `PRACTICE` va rows moi `ENGLISH_RAG` co `was_correct IS NOT NULL`.
- Test Error DNA/error capture van hoat dong khi RAG phat hien luot sua cau tieng Anh.

## Assumptions

- "Loai bo 3 che do" chi ap dung cho chat intent, khong xoa lesson practice UI.
- Qdrant source cho personal facts la Mem0 user memory, khong phai static `corpus`.
- Progress trong chat duoc tra loi bang context Postgres thay vi intent rieng `PROGRESS`.
- Response nguoi dung la natural language; metadata noi bo van duoc giu de cac co che con lai trong graph tiep tuc hoat dong.
