# English Error Span Delta Evaluation

## Scope

This run compares Gemini-generated gold incorrect spans against spans returned by the live chat system.

## Run Metadata

| Field | Value |
|---|---|
| run_id | english_error_span_delta_100_detection_rate_20260515_live_check |
| started_at | 2026-05-15T13:18:26+00:00 |
| ended_at | 2026-05-15T13:26:25+00:00 |
| backend_url | http://localhost:8000 |
| suite | english_error_span_delta |
| dataset | D:\porjects\A20-App-134\data\raw\huggingface\reddit_multigec\reddit_multi_gec_english.csv |
| sample_size | 100 |
| gold_model | gemini-2.5-pro |

## Metrics

| Metric | Value |
|---|---:|
| total_cases | 100 |
| ok_cases | 1 |
| failed_requests | 99 |
| gold_failed | 0 |
| format_compliance_rate | 0.01 |
| span_precision | 0.0 |
| span_recall | 0.0 |
| span_f1 | 0.0 |
| average_error_detection_rate_per_sentence | 0.0 |
| mean_sentence_span_recall | 0.0 |
| mean_sentence_span_precision | 0.0 |
| mean_sentence_span_f1 | 0.0 |
| matched_spans | 0 |
| gold_spans | 847 |
| system_spans | 0 |
| sentence_full_match_rate | 0.0 |
| latency_ms | {'p50': 4375.0, 'p95': 4375.0} |

## Top Missed Spans

| Span | Count |
|---|---:|
| and | 10 |
| with | 6 |
| people | 5 |
| you'd | 4 |
| maybe | 4 |
| just | 4 |
| but | 4 |
| was | 4 |
| groupexposed | 3 |
| slams | 3 |
| get | 3 |
| over | 3 |
| it's | 3 |
| so | 3 |
| is | 3 |
| yeah | 3 |
| then | 3 |
| you're | 2 |
| says | 2 |
| your | 2 |

## Sample Results

| Dataset index | Status | Gold spans | System spans | Recall | Precision |
|---|---|---|---|---:|---:|
| 0 | parse_error | ["considers", "UK exit", "banking Right, but", "you're", "the 4k", "you'd", "holding", "then dumping"] | [] | 0.00 | 0.00 |
| 1 | parse_error | ["Driver", "banned in UK", "They", "cubeWouldn't"] | [] | 0.00 | 0.00 |
| 2 | parse_error | ["Calls for fast food tax to turn 'industry on its head'", "says", "impact", "the Supermarkets", "your", "KFC's"] | [] | 0.00 | 0.00 |
| 3 | parse_error | ["Is Said to Start", "Next Week", "targeting", "Sanctuary Cities", "Surely", "they’ll", "Maybe…", "texas"] | [] | 0.00 | 0.00 |
| 4 | parse_error | ["Loved", "Just a", "nice", "hang in"] | [] | 0.00 | 0.00 |
| 5 | parse_error | ["We have freedom of speech in EU,", "say whatever they want", "if it is far right", "npr"] | [] | 0.00 | 0.00 |
| 6 | parse_error | ["canceled", "And"] | [] | 0.00 | 0.00 |
| 7 | parse_error | ["groupexposed", "investigationHe", "it though", "necessary.The", "Blair and"] | [] | 0.00 | 0.00 |
| 8 | parse_error | ["canceled They", "point it's", "laughable", "We will if", "I'm VERA eligible, talked", "much", "FERS supplement", "said | [] | 0.00 | 0.00 |
| 9 | parse_error | ["flock", "numbers", "Yeah,I'm equally jealous,", "I'm currently designing", "2kw", "because it's always struck me as st | [] | 0.00 | 0.00 |
| 10 | parse_error | ["Ok.", "Well", "dont", "GF", "attendant, when", "greet you, you", "double sure", "confortable", "7", "is not", "suck, m | [] | 0.00 | 0.00 |
| 11 | parse_error | ["topples", "top", "spot", "Obviously", "away"] | [] | 0.00 | 0.00 |
| 12 | parse_error | ["Minister", "rules out", "UK", "pan-Europe", "agreement what", "is there for", "and what specifically would be the prob | [] | 0.00 | 0.00 |
| 13 | parse_error | ["canceled IRS", "even for", "you don’t know what you’re talking about", "and", "has nothing to do with", "what state yo | [] | 0.00 | 0.00 |
| 14 | parse_error | ["slams", "scary", "just cannot see by", "have"] | [] | 0.00 | 0.00 |
| 15 | parse_error | ["combatting", "by", "mating", "click bating"] | [] | 0.00 | 0.00 |
| 16 | parse_error | ["being", "mainly", "less face to face interactions", "like to be", "a street", "but note I have a major social anxiety" | [] | 0.00 | 0.00 |
| 17 | parse_error | ["2", "state", "I’d return", "get", "get back", "you’re doing this because your plan is to get it", "or similar", "I’d r | [] | 0.00 | 0.00 |
| 18 | parse_error | ["faces", "fresh", "over", "£3bn"] | [] | 0.00 | 0.00 |
| 19 | parse_error | ["MP’s", "‘damaging’", "‘unenforceable’ >", "just", "make up", "absolutely desperate"] | [] | 0.00 | 0.00 |
| 20 | parse_error | ["is going to know", "I mean,", "you're", "asking", "it's", "Yes.", "Going to a workplace and asking everyone there", "w | [] | 0.00 | 0.00 |
| 21 | parse_error | ["Man", "threw away", "admits", "'game over' Sounds", "dude", "took off", "I guess"] | [] | 0.00 | 0.00 |
| 22 | parse_error | ["countries’", "slams", "balance'", "cynical before", "functionally", "alcohol free", "good", "in", "mates", "are", "les | [] | 0.00 | 0.00 |
| 23 | parse_error | ["wanna", "always did", "...but"] | [] | 0.00 | 0.00 |
| 24 | parse_error | ["Triple lock", "by new pensions minister", "That’s wrong,", "ISA", "actual rich", "20k", "matter to them", "great mecha | [] | 0.00 | 0.00 |
| 25 | ok | ["groupexposed", "investigationThe", "are", "ran", "in the interest of", "people you happen to have mentioned", "does st | [] | 0.00 | 0.00 |
| 26 | parse_error | ["world’s", "claims BrewDog founder", "slams", "odd", "makes money selling to", "in"] | [] | 0.00 | 0.00 |
| 27 | parse_error | ["warned not to cosy up to", "new poll shows", "Not to mention that", "No-one", "is going to inherit anything but the ri | [] | 0.00 | 0.00 |
| 28 | parse_error | ["'robustly'", "UK user ages", "July Did", "because for a time we had better alternatives", "came up", ").If", "If anyth | [] | 0.00 | 0.00 |
| 29 | parse_error | ["Football", "lead the charge", "thanks", "corrected"] | [] | 0.00 | 0.00 |
| 30 | parse_error | ["Man", "threw away", "finally admits", "analysis.Why", "analyse", "shitting myself"] | [] | 0.00 | 0.00 |
| 31 | parse_error | ["'robustly'", "UK user ages", "July I know that.", "years. It’s not working."] | [] | 0.00 | 0.00 |
| 32 | parse_error | ["rising", "we", "looked at", "find out why", "forgot to mention", "computer games.", "Banning", "DOOM", "Duke Nukem", " | [] | 0.00 | 0.00 |
| 33 | parse_error | [">David Wants to Fly is a 2010 German documentary film that follows its director, Berlin-based, film school graduate Da | [] | 0.00 | 0.00 |
| 34 | parse_error | ["Candy", "Only", "Saturday's"] | [] | 0.00 | 0.00 |
| 35 | parse_error | ["bill", "is", "these kinds of things", "produced", "It", "for trends in population to be spotted"] | [] | 0.00 | 0.00 |
| 36 | parse_error | ["resigned", "as Treasury minister", "think this is a clever bit of insight"] | [] | 0.00 | 0.00 |
| 37 | parse_error | ["LACPLESIS", "had some grudge", "againt", "Fr tho,", "kinda", "But then again", "with a tinge of sweetness to it", "was | [] | 0.00 | 0.00 |
| 38 | parse_error | ["outlines", "modernise", "Yeah", "that's a big gauntlet", "won't compete", "compete to have good", "want it", "the worl | [] | 0.00 | 0.00 |
| 39 | parse_error | ["put", "vs", "Fed", "is a different animal"] | [] | 0.00 | 0.00 |
| 40 | parse_error | ["rename", "come", "Estonia"] | [] | 0.00 | 0.00 |
| 41 | parse_error | ["over", "about", "Anyone else dislike", "the people who", "the word", "brigade"] | [] | 0.00 | 0.00 |
| 42 | parse_error | ["Difference between avslutar and slutar?", "Interesting seeing", "that", "thought", "tieing", "getting it done", "is ju | [] | 0.00 | 0.00 |
| 43 | parse_error | ["Diminitives", "That's", "On", "Cooool"] | [] | 0.00 | 0.00 |
| 44 | parse_error | ["Lots of", "on going", "micro plastics", "Including", "natural", "occuring", "Algie", "andenzymes", "Source me:", "i",  | [] | 0.00 | 0.00 |
| 45 | parse_error | ["gamble on their career", "says chief superintendent", "And", "are in a split second", "too"] | [] | 0.00 | 0.00 |
| 46 | parse_error | ["sounds like", "maybe", "some aspects", "means", "a lot of"] | [] | 0.00 | 0.00 |
| 47 | parse_error | ["urged", "push for", "get", "$300bn", "assets No", "NI", "Union other than NI has"] | [] | 0.00 | 0.00 |
| 48 | parse_error | ["to demand", "bigger", "in new headache for", "Daily reminder", "are paid", "the average of", "train drivers", "almost" | [] | 0.00 | 0.00 |
| 49 | parse_error | ["hispanics", "US", "employment opportunity", "is", "as good", "And", "labor market there", "is mostly", "Moroccan", "it | [] | 0.00 | 0.00 |
