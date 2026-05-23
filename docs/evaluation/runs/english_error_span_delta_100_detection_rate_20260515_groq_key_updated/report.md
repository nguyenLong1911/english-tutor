# Báo cáo đánh giá khả năng nhận diện lỗi tiếng Anh trong câu chat

## Mục tiêu đánh giá

Báo cáo này đánh giá khả năng của hệ thống chat trong việc nhận diện các đoạn văn bản sai trong câu tiếng Anh do người học nhập. Mỗi câu đầu vào được xem như một câu chat thực tế của người học. Hệ thống không bị chấm ở phần giải thích hay sửa câu hoàn chỉnh; lần chạy này chỉ chấm việc hệ thống có trả về đúng các span lỗi, tức các cụm từ hoặc đoạn ký tự sai được chép nguyên văn từ câu gốc hay không.

Nói ngắn gọn, bài đánh giá trả lời câu hỏi: khi người học gửi một câu tiếng Anh có lỗi, hệ thống có phát hiện đúng những phần cần sửa trong câu đó không?

## Kết luận nhanh

- Bộ đánh giá chạy đủ 100 câu, tất cả 100 request đều hoàn thành, không có request lỗi.
- Hệ thống tuân thủ định dạng đầu ra 100%, tức luôn trả về JSON array như yêu cầu của bài test.
- Precision theo span đạt 82.09%: đa số span mà hệ thống đã đánh dấu là lỗi thật theo nhãn tham chiếu.
- Recall theo span đạt 19.48%: hệ thống còn bỏ sót nhiều lỗi trong câu người học.
- Tỷ lệ phát hiện lỗi trung bình theo từng câu là 23.44%. Có thể hiểu là với một câu có nhiều lỗi, hệ thống phát hiện được khoảng một phần tư số lỗi cần tìm.
- Tỷ lệ khớp hoàn toàn cả câu là 2.00%, nghĩa là chỉ khoảng 2 trên 100 câu có danh sách lỗi được hệ thống trả về khớp hoàn toàn với nhãn tham chiếu.
- Độ trễ ở mức p50 1882 ms và p95 3218 ms trong lần chạy này.

Diễn giải tổng quan: hệ thống đang khá thận trọng. Khi đã chỉ ra một lỗi thì xác suất đúng tương đối cao, nhưng hệ thống chưa phát hiện đủ số lỗi có trong câu chat của người học. Điểm cần cải thiện chính là tăng recall mà không làm precision giảm quá mạnh.

## Nguồn gốc dataset

| Hạng mục | Giá trị |
|---|---|
| Dataset gốc | `lang-uk/Reddit-MultiGEC` trên Hugging Face |
| File gốc khai báo trong harness | `https://huggingface.co/datasets/lang-uk/Reddit-MultiGEC/resolve/main/reddit_multi_gec.csv` |
| Bản dữ liệu tiếng Anh trong repo | `data/raw/huggingface/reddit_multigec/reddit_multi_gec_english.csv` |
| Snapshot dùng cho lần chạy | `data/evaluation/runs/english_error_span_delta_100_detection_rate_20260515_groq_key_updated/dataset_snapshot.csv` |
| Số ví dụ được trích | 100 ví dụ đầu tiên thuộc ngôn ngữ tiếng Anh có cặp `text` và `correction` khác nhau |
| Mã kiểm tra nội dung dataset | `4ef1cab183bca60336f0c64d4e46768382c8b85cd364ab074bd90c89ffe74da1` |

Reddit-MultiGEC là dataset gồm các câu do người dùng Reddit viết và câu đã được sửa. Trong lần đánh giá này, chỉ các dòng tiếng Anh được dùng. Mỗi dòng có `text` là câu gốc của người học và `correction` là phiên bản đã sửa. Từ cặp câu này, bộ đánh giá tạo ra danh sách các span sai để làm nhãn tham chiếu.

## Quá trình đánh giá

1. Bộ chạy lấy 100 ví dụ tiếng Anh từ Reddit-MultiGEC. Mỗi ví dụ gồm câu gốc của người học và câu đã được sửa.
2. Gemini 2.5 Pro được dùng để tạo nhãn tham chiếu `gold_spans`: các đoạn trong câu gốc bị xem là lỗi và cần sửa. Đây là nhãn tham chiếu do mô hình tạo, không phải nhãn thủ công của con người.
3. Với từng câu gốc, bộ chạy gửi yêu cầu đến backend chat tại `http://localhost:8000`. Prompt yêu cầu hệ thống chỉ trả về JSON array gồm các đoạn sai được chép nguyên văn từ câu người học.
4. Kết quả hệ thống trả về được gọi là `system_spans`. Bộ chấm so sánh `system_spans` với `gold_spans`.
5. Một span được tính là đúng khi nó khớp với một lỗi trong nhãn tham chiếu theo logic chấm của suite `english_error_span_delta`. Sau đó bộ chấm tính precision, recall, F1, tỷ lệ khớp hoàn toàn theo câu và độ trễ.

Phạm vi đánh giá chỉ là nhận diện vị trí/nội dung lỗi trong câu chat. Báo cáo này không đánh giá chất lượng câu sửa cuối cùng, mức độ tự nhiên của lời giải thích, hay trải nghiệm hội thoại.

## Thông tin lần chạy

| Trường | Giá trị |
|---|---|
| run_id | `english_error_span_delta_100_detection_rate_20260515_groq_key_updated` |
| started_at | `2026-05-15T13:47:17+00:00` |
| ended_at | `2026-05-15T13:50:17+00:00` |
| backend_url | `http://localhost:8000` |
| suite | `english_error_span_delta` |
| sample_size | `100` |
| gold_model | `gemini-2.5-pro` |
| system_output_format | `json_array_of_incorrect_spans` |
| requires_live_provider | `gemini, groq` |

## Kết quả định lượng

| Chỉ số | Giá trị | Ý nghĩa |
|---|---:|---|
| `total_cases` | 100 | Tổng số câu chat được đánh giá. |
| `ok_cases` | 100 | Số câu được backend xử lý thành công. |
| `failed_requests` | 0 | Số request lỗi khi gọi backend. |
| `gold_failed` | 0 | Số ví dụ không tạo được nhãn tham chiếu. |
| `format_compliance_rate` | 100.00% | Tỷ lệ output đúng định dạng JSON array. |
| `span_precision` | 82.09% | Trong các lỗi hệ thống đánh dấu, tỷ lệ đánh dấu đúng. |
| `span_recall` | 19.48% | Trong các lỗi tham chiếu, tỷ lệ hệ thống phát hiện được. |
| `span_f1` | 31.49% | Điểm cân bằng giữa precision và recall theo span. |
| `average_error_detection_rate_per_sentence` | 23.44% | Trung bình mỗi câu, hệ thống phát hiện được bao nhiêu phần lỗi cần tìm. |
| `mean_sentence_span_precision` | 69.25% | Precision trung bình tính riêng từng câu rồi lấy trung bình. |
| `mean_sentence_span_f1` | 32.80% | F1 trung bình tính riêng từng câu rồi lấy trung bình. |
| `matched_spans` | 165 | Tổng số span hệ thống phát hiện đúng. |
| `gold_spans` | 847 | Tổng số span lỗi trong nhãn tham chiếu. |
| `system_spans` | 201 | Tổng số span lỗi hệ thống trả về. |
| `sentence_full_match_rate` | 2.00% | Tỷ lệ câu có toàn bộ danh sách lỗi khớp hoàn toàn. |
| `latency_ms.p50` | 1882 ms | Một nửa request có độ trễ thấp hơn mức này. |
| `latency_ms.p95` | 3218 ms | 95% request có độ trễ thấp hơn mức này. |

## Các lỗi bị bỏ sót nhiều nhất

Bảng dưới liệt kê những span xuất hiện nhiều trong nhãn tham chiếu nhưng hệ thống không phát hiện. Các span ngắn như `and`, `with`, `is` thường đại diện cho lỗi ngữ pháp hoặc lỗi nối câu theo ngữ cảnh, không nhất thiết tự bản thân từ đó luôn sai.

| Span bị bỏ sót | Số lần |
|---|---:|
| `and` | 10 |
| `with` | 6 |
| `people` | 5 |
| `you'd` | 4 |
| `maybe` | 4 |
| `just` | 4 |
| `but` | 4 |
| `slams` | 3 |
| `get` | 3 |
| `over` | 3 |
| `so` | 3 |
| `is` | 3 |
| `yeah` | 3 |
| `you're` | 2 |
| `says` | 2 |
| `much` | 2 |
| `it's` | 2 |
| `threw away` | 2 |
| `good` | 2 |
| `in` | 2 |

## Nhận xét chính

- Hệ thống ổn định về mặt kỹ thuật trong lần chạy này: 100/100 request thành công và định dạng output đạt 100%.
- Precision cao hơn recall rõ rệt. Điều này cho thấy hệ thống ít đánh dấu sai, nhưng bỏ qua nhiều lỗi thật trong câu người học.
- Tổng số lỗi tham chiếu là 847 span, nhưng hệ thống chỉ trả về 201 span và khớp đúng 165 span. Chênh lệch này giải thích vì sao recall thấp.
- Chỉ 2% câu khớp hoàn toàn với nhãn tham chiếu. Với bài toán phản hồi học tiếng Anh, điều này có nghĩa là người học vẫn có thể không được chỉ ra đầy đủ các lỗi trong một câu dài hoặc nhiều lỗi.
- Các câu dài, chứa nhiều mệnh đề, dấu câu thiếu, văn phong Reddit hoặc lỗi nối câu là nhóm dễ làm hệ thống bỏ sót.

## Phụ lục: 100 ví dụ đã đánh giá

Bảng này trích đủ 100 ví dụ của lần chạy. Cột `Câu người học` là câu chat gốc từ dataset; `Gold spans` là lỗi tham chiếu; `System spans` là lỗi hệ thống nhận diện được. Nội dung dài được rút gọn để báo cáo dễ đọc, dữ liệu đầy đủ nằm trong `results.jsonl`.

| # | Dataset index | Câu người học | Gold spans | System spans | Recall | Precision |
|---:|---:|---|---|---|---:|---:|
| 1 | 0 | Santander considers UK exit amid frustrations with high street banking Right, but if you're going the cash route and only have the 4k for the year you'd get the best r... | ["considers", "UK exit", "banking Right, but", "you're", "the 4k", "you'd", "holding", "then dumping"] | ["Right,"] | 0.12 | 1.00 |
| 2 | 1 | Driver stopped in Tesla Cybertruck banned in UK > They should crush it into a cubeWouldn't take much | ["Driver", "banned in UK", "They", "cubeWouldn't"] | ["Driver stopped in Tesla Cybertruck banned in UK", "Wouldn't take much"] | 0.25 | 0.50 |
| 3 | 2 | Calls for fast food tax to turn 'industry on its head' Good for you. It says it will also impact the Supermarkets, so it isn't just your McDonald's and KFC's. | ["Calls for fast food tax to turn 'industry on its head'", "says", "impact", "the Supermarkets", "your", "KFC's"] | ["'industry on its head' Good", "KFC's"] | 0.17 | 0.50 |
| 4 | 3 | Trump’s Deportation Plan Is Said to Start Next Week targeting Sanctuary Cities I wonder why they don’t start in the red states? Surely they’ll have an easier time. May... | ["Is Said to Start", "Next Week", "targeting", "Sanctuary Cities", "Surely", "they’ll", "Maybe…", "texas"] | ["Is", "Week targeting", "texas"] | 0.38 | 1.00 |
| 5 | 4 | Is Brno worth visiting?Loved Brno. Just a nice town to hang in with kids. | ["Loved", "Just a", "nice", "hang in"] | ["Loved", "hang in"] | 0.50 | 1.00 |
| 6 | 5 | WEF - Schulz - We have freedom of speech in EU, everyone can say whatever they want, except if it is far right Leva gre lahko tudi gor/dol. Razlika je v liberalnem ali... | ["We have freedom of speech in EU,", "say whatever they want", "if it is far right", "npr"] | ["far right Leva gre lahko tudi gor/dol", "npr stalinizem vs. hipiji"] | 0.25 | 0.50 |
| 7 | 6 | GS12 120k FJO canceled And the guy who gave him the pen | ["canceled", "And"] | ["canceled And"] | 0.50 | 1.00 |
| 8 | 7 | Far-right groupexposed in undercover BBC investigationHe will never do it though as he doesn’t believe it is necessary.The floodgates opened under Blair and now any se... | ["groupexposed", "investigationHe", "it though", "necessary.The", "Blair and"] | ["groupexposed", "investigationHe"] | 0.40 | 1.00 |
| 9 | 8 | GS12 120k FJO canceled They aren't laying off anyone (yet). At this point it's laughable. We will if RIFs, VSIPs, or VERAs come into play.I'm VERA eligible, talked to... | ["canceled They", "point it's", "laughable", "We will if", "I'm VERA eligible, talked", "much", "FERS supplement", "said a lot of people do it", "j... | ["GS12 120k FJO canceled", "We will if RIFs, VSIPs, or VERAs come into play.", "I'm VERA eligible, talked to a friend in Retirements today."] | 0.18 | 0.67 |
| 10 | 9 | UK homeowners flock to heat pumps but numbers still well below targets Yeah,I'm equally jealous,I'm currently designing a tower mount so that a 2kw array can track the... | ["flock", "numbers", "Yeah,I'm equally jealous,", "I'm currently designing", "2kw", "because it's always struck me as strange", "we adjust where po... | [] | 0.00 | 0.00 |
| 11 | 10 | Should I cancel my trip? Ok. Well there’s always a first time! Like everyone else, I dont think you should cancel. Here are a few tips: My GF is a flight attendant, wh... | ["Ok.", "Well", "dont", "GF", "attendant, when", "greet you, you", "double sure", "confortable", "7", "is not", "suck, make", "audibles", "noise ca... | ["dont", "confortable", "your planning", "security advice", "opposite from", "you'll have to trust", "it's part of it", "The things that are really... | 0.18 | 0.60 |
| 12 | 11 | Britain topples Germany to become Europe’s top investment spot Obviously they want the private companies to “invest” away our public resources even more…. | ["topples", "top", "spot", "Obviously", "away"] | ["spot Obviously", "invest"] | 0.20 | 0.50 |
| 13 | 12 | Minister rules out UK joining pan-Europe trade agreement what evidence is there for that list and what specifically would be the problem with each of them?this topic u... | ["Minister", "rules out", "UK", "pan-Europe", "agreement what", "is there for", "and what specifically would be the problem", "them?this", "usually... | ["pan-Europe", "agreement what", "?this", "US style"] | 0.29 | 1.00 |
| 14 | 13 | GS12 120k FJO canceled IRS isn’t even for sales tax so you don’t know what you’re talking about and the IRS has nothing to do with what state you’re in. Maybe educate... | ["canceled IRS", "even for", "you don’t know what you’re talking about", "and", "has nothing to do with", "what state you’re in", "Maybe", "what th... | ["canceled IRS", "sales tax so"] | 0.10 | 0.50 |
| 15 | 14 | UK ‘one of world’s least work-oriented countries’ claims BrewDog founder - as he slams obsession with 'work-life balance' It's scary how many business owners just cann... | ["slams", "scary", "just cannot see by", "have"] | ["by their employees don't have"] | 0.25 | 1.00 |
| 16 | 15 | The Birmingham women combatting loneliness by speed mating It feels so much dirtier when it's the BBC that's click bating salaciously. | ["combatting", "by", "mating", "click bating"] | ["combatting", "speed mating", "click bating"] | 0.75 | 1.00 |
| 17 | 16 | Apps to make friends I believe young people being less social is a global phenomenon caused mainly by social media and less face to face interactions in general. I per... | ["being", "mainly", "less face to face interactions", "like to be", "a street", "but note I have a major social anxiety", "somehow", "I think", "yo... | ["young people being less social", "me.I", "w"] | 0.21 | 1.00 |
| 18 | 17 | Can I rent 2 cars in 2 different state? If you’re paying for the local rental, I’d return it and get a new rental when you get back. If you’re doing this because your... | ["2", "state", "I’d return", "get", "get back", "you’re doing this because your plan is to get it", "or similar", "I’d rent", "with", "It is an", "... | ["2 different state"] | 0.08 | 1.00 |
| 19 | 18 | Thames Water faces fresh legal challenge over £3bn creditor loan | ["faces", "fresh", "over", "£3bn"] | ["£3bn creditor loan"] | 0.25 | 1.00 |
| 20 | 19 | Tory MP’s bill to ban marriage between cousins is ‘damaging’ and ‘unenforceable’ >why does it matter?Did I say it does?What are you trying to get at here? Can you just... | ["MP’s", "‘damaging’", "‘unenforceable’ >", "just", "make up", "absolutely desperate"] | [] | 0.00 | 0.00 |
| 21 | 20 | How is ICE/police going to know who has papers and who doesn’t? I mean, you're describing the definition of racial profiling and then asking if it's really racial prof... | ["is going to know", "I mean,", "you're", "asking", "it's", "Yes.", "Going to a workplace and asking everyone there", "wouldn't be", "require", "no... | ["ICE/police", "id", "your id", "your id"] | 0.05 | 0.25 |
| 22 | 21 | Man who accidentally threw away £600 million in Bitcoin finally admits it's 'game over' Sounds better than her leaving me for some dude in a band that never took off I... | ["Man", "threw away", "admits", "'game over' Sounds", "dude", "took off", "I guess"] | ["Man who", "off I guess"] | 0.29 | 1.00 |
| 23 | 22 | UK ‘one of world’s least work-oriented countries’ claims BrewDog founder - as he slams obsession with 'work-life balance' I was cynical before, but Lucky Saint is genu... | ["countries’", "slams", "balance'", "cynical before", "functionally", "alcohol free", "good", "in", "mates", "are", "less/no", "whatever", "the", "... | [] | 0.00 | 0.00 |
| 24 | 23 | 5 Days in Malta I wanna go there now! I mean, I always did...but now even more. | ["wanna", "always did", "...but"] | ["5 Days in Malta I", "wanna", "I always did"] | 0.67 | 0.67 |
| 25 | 24 | Triple lock was described as a 'silly system' by new pensions minister That’s wrong, ISA has no effect on the actual rich as the 20k is too low to matter to them. It i... | ["Triple lock", "by new pensions minister", "That’s wrong,", "ISA", "actual rich", "20k", "matter to them", "great mechanism", "other than", "to sa... | [] | 0.00 | 0.00 |
| 26 | 25 | Far-right groupexposed in undercover BBC investigationThe right are literally funded and ran in the interest of that small group of elite people you happen to have men... | ["groupexposed", "investigationThe", "are", "ran", "in the interest of", "people you happen to have mentioned", "does still care", "it definitely d... | ["groupexposed", "investigationThe", "ran", "workers rights", "tenant laws"] | 0.45 | 1.00 |
| 27 | 26 | UK ‘one of world’s least work-oriented countries’ claims BrewDog founder - as he slams obsession with 'work-life balance' It's odd for a company that makes money selli... | ["world’s", "claims BrewDog founder", "slams", "odd", "makes money selling to", "in"] | ["one of world’s", "claims BrewDog founder"] | 0.33 | 1.00 |
| 28 | 27 | Starmer warned not to cosy up to Trump as new poll shows Labour voters want closer EU ties instead Not to mention that care costs will wipe that out long before.No-one... | ["warned not to cosy up to", "new poll shows", "Not to mention that", "No-one", "is going to inherit anything but the rich"] | ["Not to mention that", "wipe that out", "before.No"] | 0.40 | 0.67 |
| 29 | 28 | All porn sites must 'robustly' verify UK user ages by July Did piracy decline because of enforcement, or because for a time we had better alternatives (when netflix fi... | ["'robustly'", "UK user ages", "July Did", "because for a time we had better alternatives", "came up", ").If", "If anything we", "are now seeing",... | ["stays low"] | 0.08 | 1.00 |
| 30 | 29 | British Football fans lead the charge against "Europe's n-word". thanks for the correction. I have corrected the OP. | ["Football", "lead the charge", "thanks", "corrected"] | ["thanks"] | 0.25 | 1.00 |
| 31 | 30 | Man who accidentally threw away £600 million in Bitcoin finally admits it's 'game over' Good analysis.Why don't you analyse my story about shitting myself too？ | ["Man", "threw away", "finally admits", "analysis.Why", "analyse", "shitting myself"] | ["Man", "Good analysis.Why", "？"] | 0.33 | 0.67 |
| 32 | 31 | All porn sites must 'robustly' verify UK user ages by July I know that. It’s been the case for years. It’s not working. | ["'robustly'", "UK user ages", "July I know that.", "years. It’s not working."] | ["UK user ages", "by July I"] | 0.50 | 1.00 |
| 33 | 32 | Knife crime is rising — we looked at the data to find out why They forgot to mention violent computer games. Banning DOOM and Duke Nukem is the obvious answer. | ["rising", "we", "looked at", "find out why", "forgot to mention", "computer games.", "Banning", "DOOM", "Duke Nukem", "is", "the obvious answer."] | ["why They forgot to mention violent computer games.", "Banning DOOM and Duke Nukem is the obvious answer."] | 0.18 | 1.00 |
| 34 | 33 | David Lynch ist tot: US-Filmemacher mit 78 Jahren gestorben >David Wants to Fly is a 2010 German documentary film that follows its director, Berlin-based, film school... | [">David Wants to Fly is a 2010 German documentary film that follows its director, Berlin-based, film school graduate David Sieveking, as he intera... | ["US-Filmemacher", "mit 78 Jahren gestorben"] | 0.00 | 0.00 |
| 35 | 34 | I am starting a Swedish Candy store in Los Angeles Only open on Saturday's?;) | ["Candy", "Only", "Saturday's"] | ["Only", "Saturday's", "?;)"] | 0.67 | 0.67 |
| 36 | 35 | Tory MP’s bill to ban marriage between cousins is ‘damaging’ and ‘unenforceable’ Reports on these kinds of things are not produced monthly. It takes years for trends i... | ["bill", "is", "these kinds of things", "produced", "It", "for trends in population to be spotted"] | ["MP’s"] | 0.00 | 0.00 |
| 37 | 36 | Tulip Siddiq resigned as Treasury minister Does anyone still unironically think this is a clever bit of insight? | ["resigned", "as Treasury minister", "think this is a clever bit of insight"] | ["minister Does"] | 0.00 | 0.00 |
| 38 | 37 | LACPLESIS I always knew Koknesis had some grudge againt Lāčplēsis.Fr tho, kinda surprised that anyone would seek out Lāčplēsis.But then again I myself once had Mītava... | ["LACPLESIS", "had some grudge", "againt", "Fr tho,", "kinda", "But then again", "with a tinge of sweetness to it", "was buying them", "1 time", "m... | ["LACPLESIS", "againt", "Fr tho", "Lāčplēsis.Fr"] | 0.30 | 0.75 |
| 39 | 38 | Education Secretary outlines plans to modernise education sector Yeah, that's a big gauntlet and we won't compete on a global scale against that at all.We can still co... | ["outlines", "modernise", "Yeah", "that's a big gauntlet", "won't compete", "compete to have good", "want it", "the world's biggest", "big enough",... | ["a big gauntlet", "we won't compete on a global scale against that at all.We can still compete to have good AI sector", "the UK are already really... | 0.19 | 1.00 |
| 40 | 39 | Thread for 1/27 EODs. Please put guidance as you have it. New supervisor probation vs new Fed probation is a different animal. | ["put", "vs", "Fed", "is a different animal"] | [] | 0.00 | 0.00 |
| 41 | 40 | Petition to rename Gulf of Finland Finns come from Estonia so there! | ["rename", "come", "Estonia"] | ["Petition to rename Gulf of Finland", "so there!"] | 0.33 | 0.50 |
| 42 | 41 | Warning over social media comments about Southport attack trial Anyone else dislike the people who use the word 'brigade' brigade? | ["over", "about", "Anyone else dislike", "the people who", "the word", "brigade"] | ["dislike", "brigade"] | 0.33 | 1.00 |
| 43 | 42 | Difference between avslutar and slutar? Interesting seeing other people's explanations that probably make more grammatical sense. My first thought was that avslutar is... | ["Difference between avslutar and slutar?", "Interesting seeing", "that", "thought", "tieing", "getting it done", "is just stopping", "could be"] | [] | 0.00 | 0.00 |
| 44 | 43 | Diminitives of the name Jökull? That's a name? On the list? Cooool! | ["Diminitives", "That's", "On", "Cooool"] | ["Diminitives"] | 0.25 | 1.00 |
| 45 | 44 | Revealed: drinking water sources in England polluted with forever chemicals Lots of research on going to find ways of breaking down micro plastics. Including natural o... | ["Lots of", "on going", "micro plastics", "Including", "natural", "occuring", "Algie", "andenzymes", "Source me:", "i", "speak to", "start ups", "e... | ["on going", "micro plastics", "occurring", "Algie", "andenzymes", "Source me", "i", "weve", "theres"] | 0.53 | 1.00 |
| 46 | 45 | Police fear they gamble on their career if they use force, says chief superintendent And the decisions they have to make are in a split second too | ["gamble on their career", "says chief superintendent", "And", "are in a split second", "too"] | [] | 0.00 | 0.00 |
| 47 | 46 | How is life in Latvia? Interesting! It sounds like Riga is still a developing capital, maybe a few years behind the other Baltic capitals in some aspects, but that jus... | ["sounds like", "maybe", "some aspects", "means", "a lot of"] | [] | 0.00 | 0.00 |
| 48 | 47 | Keir Starmer urged to push for Ukraine to get $300bn of frozen Russian assets No part of the Union other than NI has the right to unilaterally secede. | ["urged", "push for", "get", "$300bn", "assets No", "NI", "Union other than NI has"] | ["urged to push"] | 0.14 | 1.00 |
| 49 | 48 | Train drivers to demand bigger pay deal in new headache for Labour Daily reminder UK train drivers are paid over twice the average of Western European train drivers an... | ["to demand", "bigger", "in new headache for", "Daily reminder", "are paid", "the average of", "train drivers", "almost", "twice as much as", "high... | ["new headache for Labour Daily reminder UK", "blackmail"] | 0.10 | 1.00 |
| 50 | 49 | Why won't hispanics move to Spain instead of the US?1) employment opportunity in Spain is not as good. And the manual labor market there is mostly filled by Moroccan.2... | ["hispanics", "US", "employment opportunity", "is", "as good", "And", "labor market there", "is mostly", "Moroccan", "it's", "a lot further away",... | ["hispanics", "employment opportunity", "Moroccan", "it's"] | 0.31 | 1.00 |
| 51 | 50 | Half of new hospitals promised by Boris Johnson will not be built for decades If you think Boris getting voted in is a disgrace just wait until the electorate vote in... | ["If", "Boris getting voted in", "vote", "worse.The", "collective", "Con + Ref", "Over half the", "want", "corruption and", "characterised", "what... | ["decades If", "Boris getting voted in", "the electorate vote in someone", "swathe of the electorate apparently haven’t learned", "And from the sam... | 0.21 | 1.00 |
| 52 | 51 | ‘I doorknocked for Labour then racist deepfake ruined my life’ the almighty one will send the ghoul back to hell inshallah | ["then", "the", "almighty", "one", "inshallah"] | ["then racist deepfake"] | 0.20 | 1.00 |
| 53 | 52 | US Government to end birthright citizenshipI don't think any other country offers birthright citizenship.Is it outrageous to change this policy?My brother was born ove... | ["to end", "think", "offers", "change", "overseas", "parents work", "didn't become a citizen of that country"] | ["citizenshipI", "citizenship.Is", "parents work"] | 0.14 | 0.33 |
| 54 | 53 | How Axel Rudakubana was 'planning UK's first high school massacre' but was stopped by his dad a week before he murdered three girls in Southport rampage - as he admits... | ["dad", "offence", "I saw", "they asked people", "create", "a whole bunch of", "show them av", "relating", "minor", "asked them to make", "tbh", "y... | [] | 0.00 | 0.00 |
| 55 | 54 | Megathread: Job Offer Status TJO 12/20….. still haven’t heard anything. Was getting background investigation done still. Didn’t hear a peep from anyone for a gs7 position | ["anything", "Was getting background investigation done still", "Didn’t hear a peep from anyone for a gs7 position"] | ["still haven’t", "Was getting background investigation done still.", "gs7"] | 0.67 | 0.67 |
| 56 | 55 | What made you learn Swedish over Danish/Norwegian? I lived in Miami for a short while as a child and the heat and humidity was stifling. | ["made you learn", "over", "Danish/Norwegian", "lived in Miami for a short while", "was", "stifling"] | ["was"] | 0.17 | 1.00 |
| 57 | 56 | trying to find lullaby/game in latvian from my dads childhood.Yes! This! A bit like the “little piggy went to the market “.As far as I remember it was: cooking the por... | ["trying", "lullaby/game", "dads", "childhood.Yes!", "This!", "“little piggy went to the market “", "As far as I remember", "it was:", "stir", "pin... | ["latvian", "dads"] | 0.08 | 0.50 |
| 58 | 57 | Start date needs to be on or before 2-8 For the purposes of this memorandum, a position is not considered vacant if an individual has been given an offer of employment... | ["needs to be", "2-8", "For the purposes of", "been given an offer of employment", "prior to", "an offer letter in acceptance of"] | ["2-8"] | 0.17 | 1.00 |
| 59 | 58 | Did they contact your references? And if so, how?I didn’t get an interview, I just got a immediate Tentative job offer and went from there | ["And", "how?I", "just got", "a", "Tentative", "went from there"] | ["a immediate"] | 0.17 | 1.00 |
| 60 | 59 | Is there anything set up to protect and make sure deported people are safely and actually arriving at the countries they migrated from? Damn. I’m guessing those detent... | ["anything set up", "make sure", "deported people", "safely and actually arriving at", "Damn.", "I’m guessing", "detention areas", "whatthe", "“cag... | ["whatthe", "cages “"] | 0.17 | 1.00 |
| 61 | 60 | Was going to be my first FED job too Unfortunately its 90 days for most agencies but indefinitely for the IRS specifically | ["Was", "be", "too", "Unfortunately", "its", "but", "indefinitely"] | ["Was going to be my first FED job too", "its 90 days for most agencies but indefinitely for the IRS specifically"] | 0.29 | 1.00 |
| 62 | 61 | Need to learn Swedish accent for an acting rolea bunch of people have pasted links I’m sure are useful but some additional ”tells” for me as a Swede… - we generally ca... | ["Need", "rolea bunch", "pasted", "I’m sure are", "but some additional ”tells” for me as a Swede…", "bc", "phonetical", "neither does the /zh/ soun... | ["rolea", "phonetical", "mixup"] | 0.30 | 1.00 |
| 63 | 62 | Guess it’s finally my turn! FJO Congrats - process takes a while, I interviewed for mine in November of last year and just now going through suitability for clearance,... | ["Guess", "Congrats", "a while,", "going through", "suitability for clearance,", "def", "key -", "all that is going on"] | ["process takes a while", "just now going through suitability", "def"] | 0.38 | 1.00 |
| 64 | 63 | After traveling to 70 countries by 30, everything feels like “meh” – do world travelers learn to enjoy simple things again? Maldives take my breath off | ["After traveling", "by 30", "enjoy", "Maldives", "off"] | ["by 30", "Maldives take my breath off"] | 0.40 | 1.00 |
| 65 | 64 | Reeves committing ‘political suicide’ if she orders spending cuts, warns McDonnell > The problem is we're in debt up to the eyeballs.Ah the household income claptrap,... | ["Reeves committing", ", warns McDonnell >", "The problem is we're", "up to the eyeballs.", "Ah the household income claptrap,", "apply to", "budge... | [] | 0.00 | 0.00 |
| 66 | 65 | Chinese already speaking English French and Dutch, want to learn nordic languages. I would just choose one, as trying to learn all three will probably scramble them al... | ["Chinese", "already speaking", "want", "nordic", "just choose", "will probably", "scramble them all up", "in your brain", "seeing how similar they... | ["Chinese already speaking English French and Dutch", "nordic languages"] | 0.22 | 1.00 |
| 67 | 66 | Is 50k php enough for a budget of 4 people in Thailand? | ["50k", "php", "enough", "of", "4"] | ["php"] | 0.20 | 1.00 |
| 68 | 67 | Ministers consider ban on all UK public bodies making ransomware payments Victims are to blame for not adequately securing their data in the first place | ["consider", "ban on", "making", "are to blame", "for not adequately securing", "in the first place"] | ["consider ban"] | 0.17 | 1.00 |
| 69 | 68 | Absolutely devastated Please, where did you hear this? We are freaking out right now with a position my husband was being considered for. | ["Absolutely devastated", "Please,", "where did you hear this?", "with", "was"] | ["Absolutely devastated Please"] | 0.20 | 1.00 |
| 70 | 69 | Moving to Brno as an expat I love a word expat, it's basically an immigrant but it sounds exquisite 😂 Yup with 100k a month you will live pretty comfortable life here.... | ["love a word expat", "it's basically", "it sounds exquisite", "Yup with", "you will live", "pretty comfortable life", "People generally make", "an... | ["a word expat", "comfortable life", "40k a month"] | 0.25 | 0.67 |
| 71 | 70 | PSA: what Trump can and cannot do Thank you so much for this super helpful clarification of what's actually possible and what's not. | ["what", "can", "cannot", "do", "so much", "super", "of", "what's"] | [] | 0.00 | 0.00 |
| 72 | 71 | Two-thirds of major retailers warn they're raising prices because of Labour Budget, as pressure on Chancellor grows Prior to this we just paid the rest out in benefits... | ["they're", "because of Labour Budget", "grows", "Prior to this", "just", "rest", "right", "stay", "recoup the wealth transfer from COVID", "gotten... | ["Labour Budget", "Prior to this we just paid the rest out in benefits.", "here.The", "wind changing"] | 0.19 | 0.75 |
| 73 | 72 | Megathread: Job Offer Status IC is likely exempt, your timeline is also normal according to /r/SecurityClearance | ["is also normal"] | [", your timeline is also normal according to /r/SecurityClearance"] | 1.00 | 1.00 |
| 74 | 73 | Going to Iceland- Language learning resources while I'm there I'm a huge fan of comprehensible input; that's how I learned Icelandic. It takes a long time, but if you... | ["Iceland-", "learning", "resources", "while", "there", "I'm", "just", "eventually you will", "comprehend extremely well", "it will even", "The nic... | [] | 0.00 | 0.00 |
| 75 | 74 | UK’s millionaire exodus equal to losing 530,000 average taxpayers, study says Many leave because of the crumbling infrastructure in the U.K. | ["UK’s", "equal", ", study says", "leave", "because of", "crumbling"] | ["equal to losing", "Many"] | 0.17 | 0.50 |
| 76 | 75 | UK accused of undermining democratic rights with climate protest crackdown You blocked the road though. And your protest put my mum’s life in danger. | ["UK", "accused", "with", "climate protest crackdown", "though.", "And", "put my mum’s life in danger"] | ["UK", "crackdown You"] | 0.14 | 0.50 |
| 77 | 76 | Dzīvokļu cenasBeen looking for something like this!!! Super cool, thanks for sharing! | ["Been looking", "Super cool,", "thanks for sharing!"] | [] | 0.00 | 0.00 |
| 78 | 77 | Window to stop decline of England’s nature closing fast, watchdog says as a gardener i agree with lots of this - but would argue that trends are definitely changing fo... | ["nature closing", "as a gardener i", "lots of", "this -", "and as someone", "uni i", "way more", "bio-diverse", "farming..So i", "sightly", "you'd... | ["Window", "i", "i", "i", "i", "sightly", "allot", "degregation"] | 0.35 | 0.88 |
| 79 | 78 | Not having physical immigration documents when ICE officer approaches me >carrying I-94 is simple and easy, green card less soWhen I was a permanent resident, carrying... | ["when ICE officer approaches me >carrying I-94 is simple and easy, green card less so", "carrying my green card with me was simple and easy", ", I... | [">carrying I-94 is simple and easy, green card less soWhen"] | 0.12 | 1.00 |
| 80 | 79 | Passport Photo Search "photo" in Google maps. And before taking a picture, search for the criterias for passport photo for your country. Background layer, size etc.. | ["maps", "And", "search for", "criterias", "photo", "for", "layer", "etc.."] | ["Google maps", "criterias", ".."] | 0.25 | 0.67 |
| 81 | 80 | Sir Keir Starmer says governmentwill ‘look at every conceivable way'to stop Gerry Adams payout why don't we just pay the man and move on, Gerry Adams has been an elect... | ["says", "governmentwill", "'", "Adams", "payout why", "just", "on, Gerry", "parliament", "before he's", "legitimised", "into"] | ["governmentwill", "payout why don't we just pay the man and move on, Gerry Adams has been an elected MP with a seat in parliament before he's alre... | 0.18 | 1.00 |
| 82 | 81 | Education Secretary outlines plans to modernise education sector Then with respect, your wife is not necessary at her job. She is proving she can be replaced with a mu... | ["modernise", "Then", "necessary at", "proving", "with", "she's made her peace with", "lies", "to do", "job", "taken from her and fed to", "good",... | ["Then with respect,", "She is proving", "If she's made her peace", "that confidently lies to do her job", "and costs only 85% of what she did."] | 0.28 | 1.00 |
| 83 | 82 | Far-right groupexposed in undercover BBC investigationThere were no lies, considering there is still literally no evidence that he was a 'terrorist' whatsoever. | ["Far-right", "groupexposed", "investigationThere", "considering"] | ["groupexposed"] | 0.25 | 1.00 |
| 84 | 83 | Climate change scepticism almost extinct from UK national press Because everyone has to do it, if everyone takes that attitude it becomes “Well we’re only 10%…” and so... | ["scepticism", "almost extinct", "from UK national press", "Because everyone has to do it,", "if everyone takes that attitude it becomes “Well we’r... | ["almost extinct", "Because"] | 0.40 | 1.00 |
| 85 | 84 | Private tenants facing eviction so homeless people can live in South London flats The council usually signs on to fund a complete refurbishment of the flat at the end... | ["facing", "so", "people", "live in", "in South London flats", "usually signs on to fund", "takes over", "upgrading", "for the duration of the cont... | ["maintenance upkeep"] | 0.06 | 1.00 |
| 86 | 85 | Climate change scepticism almost extinct from UK national press Never with the magnitude or speed with which it has changed over the past few decades | ["Climate change scepticism almost extinct from UK national press", "Never with the magnitude or speed with which it has changed over the past few... | ["almost extinct", "Never with the magnitude or speed with which it has changed over the past few decades"] | 1.00 | 1.00 |
| 87 | 86 | She seems vastly smarter and more honest than her father. Kdo pa je arbiter, ki določa kaj je resnica in kaj ni? | ["vastly", "honest"] | [] | 0.00 | 0.00 |
| 88 | 87 | lol… the orange man got me Biden did not impose a hiring freeze. | ["lol", "me Biden"] | ["the orange man got me Biden"] | 0.50 | 1.00 |
| 89 | 88 | I am starting a Swedish Candy store in Los Angeles >How will you place orders and read labels?Because companies wants to sell to different countries, many uses English... | ["starting", "Candy", "Because", "wants", "different", "uses", "it comes to deals with", "parts"] | ["wants", "uses", "deals"] | 0.38 | 1.00 |
| 90 | 89 | USGS or Census? Would appreciate inputThis is also a concern, a lot of uncertainty with everything unfortunately. Do you think they are hiring low GS positions now cau... | ["Would appreciate input", "a lot of uncertainty with everything", "hiring low GS positions", "cause", "people", "and they need to fill the void bu... | ["inputThis", "now cause"] | 0.17 | 0.50 |
| 91 | 90 | Why won't hispanics move to Spain instead of the US?Yeah, its certainly a better path than coming via the border assuming you are able to qualify. | ["hispanics", "US", "Yeah", "its", "path", "coming via", "are able to"] | ["hispanics", "US?Yeah", "its"] | 0.43 | 1.00 |
| 92 | 91 | Pension fund It comes down to 2 things: Index that the fund follows and the rules of pension funds set up by the government.Since all indexes are a bit different and c... | ["fund", "2", "rules of pension funds set up", "indexes", "a bit", "compose of", "different", "then depending on the year they will perform a littl... | ["It comes down to 2 things", "Index that the fund follows and the rules of pension funds set up by the government.Since all indexes are a bit diff... | 0.10 | 1.00 |
| 93 | 92 | Train drivers to demand bigger pay deal in new headache for Labour That's most high paid jobs these days. | ["to demand", "bigger", "in new headache for Labour", "That's", "most high paid", "these days"] | ["to demand bigger pay deal", "That's most high paid jobs"] | 0.33 | 1.00 |
| 94 | 93 | PSA: Do not book with KIWI agency - they are a scam. I booked a domestic US flight that departed in more than seven days. The confirmation email mentioned that I could... | ["departed", "mentioned", "get", "very easy", "try", "BS", "was", "maybe they changed something"] | [] | 0.00 | 0.00 |
| 95 | 94 | Company run by Captain Tom's daughter folds with just £149 in assets - despite last year's accounts totalling £336,300 There is a president in America who just a week... | ["folds", "assets -", "totalling", "self enrich", "that", "pretence", "they would separate"] | ["just a week ago", "presumably self enrich", "gave the pretence they"] | 0.29 | 0.67 |
| 96 | 95 | DWP crackdown could see people banned from driving if welfare debts go unpaid I personally don't think we should be making it more difficult for people to access work.... | ["see", "go", "I personally", "think", "be making", "people", "Of course,", "can", "makes working easier for them", "make work more difficult.", "M... | [] | 0.00 | 0.00 |
| 97 | 96 | USA citizen, married to an immigrant, where should I educate myself and what should I know right now? Not sketchy at all. Anyone person who enters without inspection i... | ["USA", "educate myself", "what should I know", "Not sketchy at all.", "Anyone person", "adjust status", "married"] | ["USA citizen", "Anyone person"] | 0.29 | 1.00 |
| 98 | 97 | Defiant Starmer declares he wants 10 years as UK PM Thatcher didn’t have a mountain of misinformation in the homes of her constituents, though. | ["declares", "he wants", "10", "UK PM Thatcher"] | [] | 0.00 | 0.00 |
| 99 | 98 | IRS Honors Attorney Program- How "At-Risk"? | [] | ["Program- How"] | 1.00 | 0.00 |
| 100 | 99 | I need genuine advice on where to movei'm following the news every day (more than I should) and Trump has never said literally anything negative about skilled immigran... | ["movei'm", "should) and", "literally", "hate", "politics but", "actually mentioned", "like \\"if", "student you", "graduation\\".In", "yeah,", "wait... | ["movei'm", "\\"graduation\\".In", "waiting arms open"] | 0.23 | 1.00 |

## Tệp dữ liệu liên quan

- Manifest lần chạy: `data/evaluation/runs/english_error_span_delta_100_detection_rate_20260515_groq_key_updated/manifest.json`
- Tóm tắt số liệu: `data/evaluation/runs/english_error_span_delta_100_detection_rate_20260515_groq_key_updated/summary.json`
- Kết quả chi tiết từng ví dụ: `data/evaluation/runs/english_error_span_delta_100_detection_rate_20260515_groq_key_updated/results.jsonl`
- Snapshot 100 ví dụ: `data/evaluation/runs/english_error_span_delta_100_detection_rate_20260515_groq_key_updated/dataset_snapshot.csv`
- Gold spans dùng để chấm: `data/evaluation/runs/english_error_span_delta_100_detection_rate_20260515_groq_key_updated/gold_delta.jsonl`
