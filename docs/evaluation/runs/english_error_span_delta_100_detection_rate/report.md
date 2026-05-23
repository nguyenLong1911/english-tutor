# English Error Span Delta Evaluation

## Scope

This run compares Gemini-generated gold incorrect spans against spans returned by the live chat system.

## Run Metadata

| Field | Value |
|---|---|
| run_id | english_error_span_delta_100_detection_rate |
| started_at | 2026-05-15T13:04:34+00:00 |
| ended_at | 2026-05-15T13:07:37+00:00 |
| backend_url | http://localhost:8000 |
| suite | english_error_span_delta |
| dataset | D:\porjects\A20-App-134\data\raw\huggingface\reddit_multigec\reddit_multi_gec_english.csv |
| sample_size | 100 |
| gold_model | gemini-2.5-pro |

## Metrics

| Metric | Value |
|---|---:|
| total_cases | 100 |
| ok_cases | 99 |
| failed_requests | 1 |
| gold_failed | 0 |
| span_precision | 0.0 |
| span_recall | 0.0 |
| span_f1 | 0.0 |
| average_error_detection_rate_per_sentence | 0.0 |
| mean_sentence_span_recall | 0.0 |
| mean_sentence_span_precision | 0.0 |
| mean_sentence_span_f1 | 0.0 |
| matched_spans | 0 |
| gold_spans | 840 |
| system_spans | 0 |
| sentence_full_match_rate | 0.0 |
| latency_ms | {'p50': 1658.0, 'p95': 2496.0} |

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
| then | 3 |
| you're | 2 |
| says | 2 |
| your | 2 |
| much | 2 |

## Sample Results

| Dataset index | Status | Gold spans | System spans | Recall | Precision |
|---|---|---|---|---:|---:|
| 0 | ok | ["considers", "UK exit", "banking Right, but", "you're", "the 4k", "you'd", "holding", "then dumping"] | [] | 0.00 | 0.00 |
| 1 | ok | ["Driver", "banned in UK", "They", "cubeWouldn't"] | [] | 0.00 | 0.00 |
| 2 | ok | ["Calls for fast food tax to turn 'industry on its head'", "says", "impact", "the Supermarkets", "your", "KFC's"] | [] | 0.00 | 0.00 |
| 3 | ok | ["Is Said to Start", "Next Week", "targeting", "Sanctuary Cities", "Surely", "they’ll", "Maybe…", "texas"] | [] | 0.00 | 0.00 |
| 4 | ok | ["Loved", "Just a", "nice", "hang in"] | [] | 0.00 | 0.00 |
| 5 | ok | ["We have freedom of speech in EU,", "say whatever they want", "if it is far right", "npr"] | [] | 0.00 | 0.00 |
| 6 | ok | ["canceled", "And"] | [] | 0.00 | 0.00 |
| 7 | ok | ["groupexposed", "investigationHe", "it though", "necessary.The", "Blair and"] | [] | 0.00 | 0.00 |
| 8 | ok | ["canceled They", "point it's", "laughable", "We will if", "I'm VERA eligible, talked", "much", "FERS supplement", "said | [] | 0.00 | 0.00 |
| 9 | ok | ["flock", "numbers", "Yeah,I'm equally jealous,", "I'm currently designing", "2kw", "because it's always struck me as st | [] | 0.00 | 0.00 |
| 10 | ok | ["Ok.", "Well", "dont", "GF", "attendant, when", "greet you, you", "double sure", "confortable", "7", "is not", "suck, m | [] | 0.00 | 0.00 |
| 11 | ok | ["topples", "top", "spot", "Obviously", "away"] | [] | 0.00 | 0.00 |
| 12 | ok | ["Minister", "rules out", "UK", "pan-Europe", "agreement what", "is there for", "and what specifically would be the prob | [] | 0.00 | 0.00 |
| 13 | ok | ["canceled IRS", "even for", "you don’t know what you’re talking about", "and", "has nothing to do with", "what state yo | [] | 0.00 | 0.00 |
| 14 | ok | ["slams", "scary", "just cannot see by", "have"] | [] | 0.00 | 0.00 |
| 15 | ok | ["combatting", "by", "mating", "click bating"] | [] | 0.00 | 0.00 |
| 16 | ok | ["being", "mainly", "less face to face interactions", "like to be", "a street", "but note I have a major social anxiety" | [] | 0.00 | 0.00 |
| 17 | ok | ["2", "state", "I’d return", "get", "get back", "you’re doing this because your plan is to get it", "or similar", "I’d r | [] | 0.00 | 0.00 |
| 18 | ok | ["faces", "fresh", "over", "£3bn"] | [] | 0.00 | 0.00 |
| 19 | ok | ["MP’s", "‘damaging’", "‘unenforceable’ >", "just", "make up", "absolutely desperate"] | [] | 0.00 | 0.00 |
| 20 | ok | ["is going to know", "I mean,", "you're", "asking", "it's", "Yes.", "Going to a workplace and asking everyone there", "w | [] | 0.00 | 0.00 |
| 21 | ok | ["Man", "threw away", "admits", "'game over' Sounds", "dude", "took off", "I guess"] | [] | 0.00 | 0.00 |
| 22 | ok | ["countries’", "slams", "balance'", "cynical before", "functionally", "alcohol free", "good", "in", "mates", "are", "les | [] | 0.00 | 0.00 |
| 23 | ok | ["wanna", "always did", "...but"] | [] | 0.00 | 0.00 |
| 24 | ok | ["Triple lock", "by new pensions minister", "That’s wrong,", "ISA", "actual rich", "20k", "matter to them", "great mecha | [] | 0.00 | 0.00 |
| 25 | ok | ["groupexposed", "investigationThe", "are", "ran", "in the interest of", "people you happen to have mentioned", "does st | [] | 0.00 | 0.00 |
| 26 | ok | ["world’s", "claims BrewDog founder", "slams", "odd", "makes money selling to", "in"] | [] | 0.00 | 0.00 |
| 27 | ok | ["warned not to cosy up to", "new poll shows", "Not to mention that", "No-one", "is going to inherit anything but the ri | [] | 0.00 | 0.00 |
| 28 | ok | ["'robustly'", "UK user ages", "July Did", "because for a time we had better alternatives", "came up", ").If", "If anyth | [] | 0.00 | 0.00 |
| 29 | ok | ["Football", "lead the charge", "thanks", "corrected"] | [] | 0.00 | 0.00 |
| 30 | ok | ["Man", "threw away", "finally admits", "analysis.Why", "analyse", "shitting myself"] | [] | 0.00 | 0.00 |
| 31 | ok | ["'robustly'", "UK user ages", "July I know that.", "years. It’s not working."] | [] | 0.00 | 0.00 |
| 32 | ok | ["rising", "we", "looked at", "find out why", "forgot to mention", "computer games.", "Banning", "DOOM", "Duke Nukem", " | [] | 0.00 | 0.00 |
| 33 | ok | [">David Wants to Fly is a 2010 German documentary film that follows its director, Berlin-based, film school graduate Da | [] | 0.00 | 0.00 |
| 34 | ok | ["Candy", "Only", "Saturday's"] | [] | 0.00 | 0.00 |
| 35 | ok | ["bill", "is", "these kinds of things", "produced", "It", "for trends in population to be spotted"] | [] | 0.00 | 0.00 |
| 36 | ok | ["resigned", "as Treasury minister", "think this is a clever bit of insight"] | [] | 0.00 | 0.00 |
| 37 | ok | ["LACPLESIS", "had some grudge", "againt", "Fr tho,", "kinda", "But then again", "with a tinge of sweetness to it", "was | [] | 0.00 | 0.00 |
| 38 | ok | ["outlines", "modernise", "Yeah", "that's a big gauntlet", "won't compete", "compete to have good", "want it", "the worl | [] | 0.00 | 0.00 |
| 39 | ok | ["put", "vs", "Fed", "is a different animal"] | [] | 0.00 | 0.00 |
| 40 | ok | ["rename", "come", "Estonia"] | [] | 0.00 | 0.00 |
| 41 | ok | ["over", "about", "Anyone else dislike", "the people who", "the word", "brigade"] | [] | 0.00 | 0.00 |
| 42 | ok | ["Difference between avslutar and slutar?", "Interesting seeing", "that", "thought", "tieing", "getting it done", "is ju | [] | 0.00 | 0.00 |
| 43 | ok | ["Diminitives", "That's", "On", "Cooool"] | [] | 0.00 | 0.00 |
| 44 | ok | ["Lots of", "on going", "micro plastics", "Including", "natural", "occuring", "Algie", "andenzymes", "Source me:", "i",  | [] | 0.00 | 0.00 |
| 45 | ok | ["gamble on their career", "says chief superintendent", "And", "are in a split second", "too"] | [] | 0.00 | 0.00 |
| 46 | ok | ["sounds like", "maybe", "some aspects", "means", "a lot of"] | [] | 0.00 | 0.00 |
| 47 | ok | ["urged", "push for", "get", "$300bn", "assets No", "NI", "Union other than NI has"] | [] | 0.00 | 0.00 |
| 48 | ok | ["to demand", "bigger", "in new headache for", "Daily reminder", "are paid", "the average of", "train drivers", "almost" | [] | 0.00 | 0.00 |
| 49 | ok | ["hispanics", "US", "employment opportunity", "is", "as good", "And", "labor market there", "is mostly", "Moroccan", "it | [] | 0.00 | 0.00 |
