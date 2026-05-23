# Curriculum Skeleton — Alpha v1.0

56 YAML topic files generated theo `content_authoring_guide.md` (Sprint 0).
Mỗi YAML hiện có một file Markdown bài giảng tương ứng để hiển thị trực tiếp cho learner.

## Cấu trúc

```
curriculum/
├── A2/   (14 topics: 8 grammar + 6 vocabulary)
├── B1/   (18 topics: 10 grammar + 8 vocabulary)
├── B2/   (8 topics: 4 grammar + 4 vocabulary)
├── C1/   (8 topics: 4 grammar + 4 vocabulary)
└── C2/   (8 topics: 4 grammar + 4 vocabulary)
```

## Quy ước tên file

- File bài học được đánh số riêng trong từng subfolder: `01_`, `02_`, `03_`...
- YAML giữ metadata/máy đọc: `01_A2_present_simple_be.yaml`.
- Markdown là bài giảng thân thiện cho learner: `01_A2_present_simple_be.md`.
- `topic_id` vẫn là định danh ổn định, ví dụ `A2_present_simple_be`; số thứ tự chỉ dùng cho sắp xếp file.

## Danh sách topics

### A2 — Grammar (8)
1. `A2_present_simple_be` — Present Simple với 'to be'
2. `A2_articles` — Mạo từ a/an/the
3. `A2_basic_pronouns` — Đại từ cơ bản (incl. its/it's)
4. `A2_past_simple_regular` — Quá khứ đơn (có quy tắc)
5. `A2_past_simple_irregular` — Quá khứ đơn (bất quy tắc)
6. `A2_present_continuous` — Hiện tại tiếp diễn
7. `A2_modal_can_could` — can/could
8. `A2_prepositions_time_place` — in/on/at

### A2 — Vocabulary (6)
9. `A2_basic_business_vocab`
10. `A2_daily_routines`
11. `A2_meeting_basics`
12. `A2_numbers_dates_money`
13. `A2_common_adjectives` — incl. -ing/-ed confusion
14. `A2_email_greetings_basic`

### B1 — Grammar (10)
15. `B1_present_perfect_vs_past_simple`
16. `B1_conditionals_1_2`
17. `B1_passive_voice`
18. `B1_modals_obligation` — must/have to/should
19. `B1_comparative_superlative`
20. `B1_future_forms` — will / be going to / present continuous
21. `B1_relative_clauses`
22. `B1_gerunds_infinitives`
23. `B1_reported_speech_basics`
24. `B1_quantifiers` — some/any, much/many, few/little

### B1 — Vocabulary (8)
25. `B1_marketing_campaign_vocab` (đã có sẵn trong guide làm reference)
26. `B1_tech_basics_vocab`
27. `B1_finance_basics_vocab`
28. `B1_email_writing_vocab`
29. `B1_presentation_language_vocab`
30. `B1_travel_logistics_vocab`
31. `B1_customer_service_vocab`
32. `B1_project_management_vocab`

### B2 — Grammar (4)
33. `B2_conditionals_3_mixed`
34. `B2_reported_speech_advanced`
35. `B2_advanced_passives`
36. `B2_inversion_emphasis`

### B2 — Vocabulary (4)
37. `B2_stakeholder_communication_vocab`
38. `B2_technical_specs_vocab`
39. `B2_financial_reporting_vocab`
40. `B2_negotiation_language_vocab`

### C1 — Grammar (4)
41. `C1_subjunctive_unreal_past` — Subjunctive và Unreal Past
42. `C1_advanced_modal_verbs` — Modal Verbs nâng cao (suy luận, nuối tiếc)
43. `C1_complex_noun_phrases` — Cụm danh từ phức tạp và Nominalization
44. `C1_discourse_cohesion` — Discourse Markers và Cohesion nâng cao

### C1 — Vocabulary (4)
45. `C1_strategic_planning_vocab`
46. `C1_legal_contracts_vocab`
47. `C1_academic_writing_vocab`
48. `C1_crisis_communication_vocab`

### C2 — Grammar (4)
49. `C2_ellipsis_substitution` — Ellipsis và Substitution
50. `C2_advanced_concession_contrast` — Cấu trúc nhượng bộ và đối lập nâng cao
51. `C2_register_style_control` — Kiểm soát Register và Style
52. `C2_rhetorical_devices` — Rhetorical Devices trong thuyết trình

### C2 — Vocabulary (4)
53. `C2_c_suite_communication_vocab`
54. `C2_cross_cultural_pragmatics_vocab`
55. `C2_data_driven_storytelling_vocab`
56. `C2_advanced_hedging_stance_vocab`

## QA đã chạy

Mọi file đã pass checklist 3.5 trong guide:
- `topic_id` trùng phần định danh sau số thứ tự trong tên file
- 3-5 objectives, ≥2 common_errors (đủ wrong/correct/hint)
- mastery có min_exercises + accuracy_threshold
- exercise_types 2-4 loại từ danh sách chuẩn
- prerequisites ≤ 3 (theo FAQ)
- Mọi prerequisite reference đều tồn tại trong bộ
- Mọi `recommended_vocab` đều khớp với word có trong vocabulary seed sample (section 2.2 của guide)
- YAML syntax valid

## Lưu ý cho content reviewer

1. **Common errors có ưu tiên interference errors từ tiếng Việt** (theo FAQ guide):
   - Cấu trúc `discuss about` (sai), `responsible of` (sai), `agree with` vs `I'm agree`
   - Lỗi trật tự tính từ–danh từ
   - Lỗi `fastly` (không tồn tại)
   - Lỗi `boring/bored`, `interesting/interested`
2. **`recommended_vocab` chỉ ref tới các word trong seed sample** của guide (15 từ ví dụ). Khi seed CSV đầy đủ 3,500 từ, có thể mở rộng.
3. **Prerequisites tạo thành 1 DAG hợp lệ** — A2 grammar là root, các B1/B2 topics phụ thuộc theo logic sư phạm.
4. **Đề xuất bước tiếp**: chạy `validate_curriculum.py` từ dev team (khi có) + peer review 4-5 topics random với language teacher khác.
