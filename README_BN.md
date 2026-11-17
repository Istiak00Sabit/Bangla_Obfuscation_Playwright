# Bangla Obfuscation — Playwright Collector

GitHub থেকে clone করলে `urls.example.txt` কপি করে `urls.txt` বানাবে। Windows batch file অনুপস্থিত `urls.txt` নিজে তৈরি করে দেয়। পরে `UPDATE_WINDOWS.bat` অথবা `git pull --ff-only` দিয়ে code update করা যাবে। তোমার স্থানীয় `urls.txt`, `data`, `.venv` ও saved browser profile git-এ track করা হয় না। Collector বন্ধ করে update করবে।

Python 3.10+ দিয়ে নিজের কম্পিউটারে চালানোর জন্য তৈরি। Facebook-এর নির্দিষ্ট URL খুলে পাওয়া পোস্ট/কমেন্টের text সংরক্ষণ, পরিচিত surface signal চিহ্নিত এবং নতুন ধরনের obfuscation manually annotate করা যায়।

**কেবল পরিচিত pattern মেলা লেখা সংগ্রহ করা হয় না।** শনাক্ত হওয়া সব text record রাখা হয়—স্বাভাবিক বাংলা, Banglish, English, code-mixed এবং signal না পাওয়া লেখাও। কোনো record স্বয়ংক্রিয়ভাবে “obfuscated”, “hate” বা “plain” label পায় না।

## আগে থেকেই login থাকা Google Chrome ব্যবহার

এই mode-এ Chrome-এর C-drive profile দ্বিতীয়বার launch বা cookie file copy করা হয় না। তোমার চালু Chrome-এর অনুমোদিত debugging connection ব্যবহার করে একই logged-in session-এর মধ্যে একটি নতুন tab খোলা হয়। Tool শুধু নিজের তৈরি tab বন্ধ করে; Chrome/context বন্ধ করার command দেয় না।

এই mode-এর জন্য **Playwright 1.65.2+** এবং Chrome-এ remote debugging-এর user-facing setting প্রয়োজন। তোমার Chrome-এ setting না থাকলে নিচের separate-profile mode ব্যবহার করবে। Live Windows Chrome attach এই তৈরির পরিবেশে পরীক্ষা করা যায়নি; connection ও tab-lifecycle-এর mocked tests আছে।

Windows-এ আগের ফোল্ডারের `collector.py`, `requirements.txt`, `RUN_WINDOWS.bat` ও README এই আপডেট দিয়ে replace করো। `urls.txt`, `.venv`, `data` বা আগে সংরক্ষিত profile মুছবে না। নতুন ZIP আলাদা ফোল্ডারে extract করলে সেখান থেকে এই source ফাইলগুলো পুরোনো ফোল্ডারে copy করা যায়।

1. তোমার সাধারণ Chrome-এর যে profile-এ Facebook login আছে, সেখানে address bar-এ `chrome://inspect/#remote-debugging` খোলো।
2. Remote debugging-এর switch/checkbox enable করো; Chrome চালু রাখো।
3. `urls.txt`-এ target Facebook link বসাও।
4. পুরোনো project folder-এর PowerShell-এ চালাও:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe collector.py collect --urls urls.txt --attach-chrome
```

5. Chrome connection permission চাইলে Allow দাও। Facebook session সচল থাকলে আলাদা login লাগবে না। এই mode-এ Playwright-এর Chromium download লাগে না। কাজ শেষে চাইলে Chrome-এর একই setting থেকে remote debugging বন্ধ করতে পারো।

`RUN_WINDOWS.bat`-এর **4** নম্বর option-ও একই কাজ করে; এই option Chromium install ধাপ বাদ দেয়। তোমার আগে থেকে দেওয়া `urls.txt` link ব্যবহার করবে। প্রয়োজন হলে attach command-এর শেষে `--manual` যোগ করে প্রতি source-এ All comments বেছে নেওয়ার সময় পাওয়া যায়।

এই mode-এ `--headless` ব্যবহার করা যাবে না। `--profile`/`--browser-executable` দিয়ে অন্য profile/browser খোলা হয় না। Windows-এর Chrome সেটিং, user permission, Playwright compatibility বা managed-browser policy-এর কারণে connection ব্যর্থ হতে পারে; code তখন সংশ্লিষ্ট error দেখায়। এটি raw cookie export করে না এবং browser-এর স্বাভাবিক permission prompt এড়িয়ে যায় না।

## Ubuntu-তে শুরু

ZIP extract করে এই ফোল্ডারে terminal খুলো:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Browser-এর Linux system dependency missing দেখালে Playwright-এর নির্দেশনা অনুযায়ী `python -m playwright install-deps chromium` চালাতে হতে পারে।

`urls.txt`-এ আসল Facebook page/post link বসাও, প্রতি লাইনে একটি। শুরুতে কয়েকটি individual post link দিলে comments পরীক্ষা করা সহজ হবে। `#` দিয়ে শুরু হওয়া লাইন বাদ যায়।

Login প্রয়োজন হলে:

```bash
python collector.py login
```

Browser খুললে তুমি নিজে Facebook login করবে। Login/verification শেষ করে terminal-এ Enter চাপবে। Password code/config-এ লিখতে হয় না; browser profile তোমার কম্পিউটারে থাকে। সাধারণ Chrome-এর profile ব্যবহার না করে টুলের আলাদা profile ব্যবহার করো।

তারপর:

```bash
python collector.py collect --urls urls.txt --manual
```

প্রতি URL খুললে browser-এ প্রয়োজনমতো **All comments** নির্বাচন, প্রাসঙ্গিক thread খোলা এবং popup বন্ধ করে terminal-এ Enter চাপো। এরপর tool পরিচিত read/expand button ব্যবহার করে, scroll করে এবং পাওয়া text save করে। `--manual` বাদ দিলে শুরুতে এই বিরতি থাকবে না।

একটি সরাসরি URL দিয়েও চালানো যায়:

```bash
python collector.py collect --url "https://www.facebook.com/PAGE/posts/POST_ID" --manual
```

URL-টি নিজের আসল link দিয়ে বদলাবে। কাজ থামাতে Ctrl+C; ইতিমধ্যে পাওয়া record save/export হবে।

## Windows-এ শুরু

Python 3.10+ install করা থাকলে `RUN_WINDOWS.bat` খুলো। 1 = আলাদা browser-এ login, 2 = সেই browser দিয়ে `urls.txt` থেকে collect, 3 = local demo, 4 = আগে থেকেই login থাকা Chrome-এ connect। Separate browser ব্যবহার করলে শুরুতে একবার 1, তারপর আবার খুলে 2 বেছে নেওয়া যায়।

অথবা PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe collector.py login
.\.venv\Scripts\python.exe collector.py collect --urls urls.txt --manual
```

## কোন ফাইল কী কাজে লাগবে

| ফাইল | বিষয় |
|---|---|
| `data/records.jsonl` | মূল dataset: raw text, দৃশ্যমান text, context, source, capture time, signals ও human annotation। |
| `data/all_records.csv` | সব record; প্রথম review এই ফাইল থেকে করবে। |
| `data/surface_candidates.csv` | কেবল কিছু surface signal মেলা record; এটি সব obfuscation-এর তালিকা নয়। |
| `data/annotation_types.json` | ২২টি প্রাথমিক annotation type; নিজের নতুন label যোগ করা যায়। |
| `data/media.jsonl` | পোস্টে পাওয়া বড় rendered image-এর URL/alt text; visual review বাকি বলে চিহ্নিত। |
| `data/revisions.jsonl` | “See more” খোলার পরে text বদলালে আগের সংস্করণ। |
| `data/crawl_log.jsonl` | প্রতিটি source-এ কোথায় থেমেছে, কোনো login/block/error ছিল কি না। |
| `data/summary.json` | মোট record, signal পাওয়া record ও media review count। |

`raw_text`-এ Unicode normalization, symbol removal বা space removal করা হয় না। JSONL-এ zero-width এবং combining mark আলাদাভাবে অক্ষুণ্ণ থাকে। Signal-এর start/end হলো মূল `raw_text`-এর zero-based Python Unicode code-point offset।

Spreadsheet formula হিসেবে text চালু হওয়া ঠেকাতে CSV-এর `=`, `+`, `-`, `@` দিয়ে শুরু হওয়া cell-এর আগে apostrophe দেওয়া হয়। **অপরিবর্তিত গবেষণার source হিসেবে `records.jsonl` ব্যবহার করবে।** CSV UTF-8 BOM-সহ লেখা হয়, যাতে বাংলা Excel-এ খোলে।

একই text লিখেছে এমন আলাদা comment observation রাখা হয়। `content_hash` দিয়ে exact text-এর group করা যায়; duplicate বলে আলাদা ব্যবহারকারীর সমান মন্তব্য মুছে ফেলা হয় না। একই DOM node পুনরায় দেখা গেলে update হয়। Permalink না পাওয়া record নতুন run-এ remount হলে duplicate observation থাকতে পারে।

## “সব ধরনের obfuscation” কীভাবে সামলানো হচ্ছে

স্বয়ংক্রিয়ভাবে প্রত্যেক ধরনের obfuscation চিনে ফেলার দাবি করা যায় না। বিশেষ করে context-dependent বিকৃত বানান, গোপন codeword, phonetic রূপ বা নতুন কৌশল একটি regex দিয়ে নির্ভরযোগ্যভাবে চেনা যায় না।

এই tool-এর পদ্ধতি:

1. শনাক্ত হওয়া text record-গুলো আগে রাখবে; keyword, ভাষা বা পরিচিত obfuscation দিয়ে filter করবে না।
2. Slash/symbol, অস্বাভাবিক whitespace, format/zero-width character, সংখ্যা–অক্ষর, mixed script, Latin text, repetition, emoji এবং ছোট fragment-এর মতো বৈশিষ্ট্যকে **সম্ভাব্য signal** হিসেবে দেখাবে।
3. Signal-হীন text-ও `all_records.csv`-এ থাকবে এবং `unreviewed` থাকবে।
4. Human review-তে একাধিক type, নতুন custom type, নিশ্চিত reconstruction ও uncertainty annotate করা যাবে।

প্রাথমিক annotation type-এ insertion/deletion/substitution/transposition, word splitting/merging, symbol masking, repetition, phonetic variant, grapheme/diacritic change, number rebus, script mixing/homoglyph, romanized Bangla, invisible formatting, emoji, abbreviation, semantic codeword এবং image text আছে। একাধিক type `|` দিয়ে লেখা যায়। তালিকা বন্ধ নয়।

**Signal মানেই obfuscation নয়।** বাংলায় ZWJ/ZWNJ বৈধ shaping-এর অংশ হতে পারে; emoji সাধারণ reaction হতে পারে; Latin text English-ও হতে পারে; সাধারণ ছোট শব্দ spacing signal-এ পড়তে পারে। NFC-তে text বদলানোও নিজে থেকে আক্রমণের প্রমাণ নয়।

## Manual annotation সংরক্ষণ

`all_records.csv`-এর একটি কপি `annotated.csv` নামে রাখো। কপিতে এই column-গুলো edit করবে:

| Column | কী লিখবে |
|---|---|
| `human_label` | `unreviewed`, `obfuscated`, `plain` অথবা `uncertain` |
| `normalized_text` | নিশ্চিত normalized/reconstructed text; অনিশ্চিত হলে ফাঁকা রাখো। |
| `confirmed_types` | যেমন `space_insertion|punctuation_insertion`; নতুন custom label-ও চলবে। |
| `annotation_notes` | কারণ, সম্ভাব্য বিকল্প এবং নতুন type-এর ব্যাখ্যা। |

`raw_text` বা `record_id` বদলাবে না। তারপর:

```bash
python collector.py import-review --csv annotated.csv --output data
```

এতে annotation মূল JSONL-এ যাবে এবং CSV পুনরায় তৈরি হবে। চলমান collection-এর সময় একই ফাইল edit/import করবে না। Dataset-এর আগের সংগ্রহ নিয়ে চালালে এটি append/update করে; আলাদা experiment-এর জন্য আলাদা `--output` directory দাও।

## যেসব সীমা মাথায় রেখে ফল ব্যবহার করবে

- **Facebook-এ live test করা হয়নি।** কোনো target URL/session দেওয়া হয়নি, আর তৈরির host-এ Chromium launch socket permission-এর কারণে আটকে গেছে। Data/Unicode পরীক্ষা চালানো হয়েছে; browser extraction-এর local fixture tests দেওয়া আছে, কিন্তু এখানে execute করা যায়নি।
- Selectorগুলো সাধারণ message/article structure-এর ভিত্তিতে তৈরি। Facebook-এর layout অনুযায়ী বদলাতে হতে পারে। `article_fallback_with_ui` record-এ নাম, UI text বা আশপাশের লেখা থাকতে পারে—manual cleaning লাগবে। `kind=unknown` মানে post/comment-এর নির্ভরযোগ্য পার্থক্য করা যায়নি।
- DOM থেকে পাওয়া raw text এবং মূল Facebook posting payload একই হওয়ার নিশ্চয়তা নেই। Browser/প্ল্যাটফর্ম আগেই কোনো অক্ষর বদলালে তা ফিরিয়ে আনা যায় না। `visible_text` পাশাপাশি রাখা হয় তুলনার জন্য।
- **ছবির ভেতরের লেখা এই সংস্করণে OCR করা হয় না।** `media.jsonl` একটি review manifest; image download নয়। Image-based obfuscation-এর জন্য মূল ছবি সংগ্রহ করে আলাদা OCR ও visual verification প্রয়োজন। Alt text-কে মূল ছবির transcription ধরে নেবে না।
- সব source-এর সব post/comment পাওয়ার নিশ্চয়তা নেই। Pagination, hidden/restricted/deleted content, ranking, collapsed replies, virtualized UI এবং run limit coverage কমাতে পারে। একটি finite crawl থেকে “সব ধরনের obfuscation পাওয়া গেছে” সিদ্ধান্ত নেবে না।
- সব label বাংলা/English UI-তে একই নয়। “All comments” বেছে নেওয়া না গেলে `--manual` ব্যবহার করবে। Tool শুধু কয়েকটি exact read/expand label click করে; Like/Reply/Share বা comment submit করে না।
- Login/checkpoint/CAPTCHA বা HTTP 401/403/429 পেলে থামে। Browser automation দিয়ে access restriction দূর হয় না। Logged-in profile একই সময়ে অন্য run-এ খোলা রাখবে না। নিজের browser profile বা session credentials dataset-এর সঙ্গে share করবে না।
- `captured_at_utc` হলো সংগ্রহের সময়; পোস্ট প্রকাশের সময় নয়। কোনো missing metadata বানানো হয় না।
- Raw text ও context-এ ব্যক্তির নাম/অন্যান্য তথ্য থাকতে পারে; এই সংস্করণ anonymization করে না।

আরও scroll/time দরকার হলে:

```bash
python collector.py collect --urls urls.txt --manual --max-rounds 150 --wait 2 --max-records 20000
```

`--max-records` প্রতিটি extraction batch-এর পরে পরীক্ষা করা stopping threshold; একটি batch-এর কারণে সংখ্যা সামান্য বেশি হতে পারে। Default: প্রতি URL সর্বোচ্চ 60 round, প্রতি wait 1.5 second, 3 idle round-এ থামে।

## তৈরি করা example ও পরীক্ষা

Facebook-এ না গিয়ে synthetic fixture দিয়ে চালাতে:

```bash
python collector.py demo
```

এটি `tests/fixture.html` ব্যবহার করে `demo_output` বানাবে। **এখানকার উদাহরণগুলো আমাদের তৈরি; বাস্তব Facebook corpus নয়।** কোনো Facebook request করে না। Browser চালানো যায় এমন environment লাগবে।

পূর্ণ tests:

```bash
python -m unittest discover -s tests -v
```

ইনস্টল করা Chromium binary দিয়ে test করতে চাইলে `COLLECTOR_BROWSER` environment variable বা CLI-তে `--browser-executable /path/to/chromium` দেওয়া যায়। Browser unavailable host-এ শুধু data/signal tests চালাতে Linux-এ `COLLECTOR_SKIP_BROWSER=1 python -m unittest discover -s tests -v` ব্যবহার করা যায়; এই skip-কে browser test pass হিসেবে গণনা করবে না।

Official references:

- [Playwright persistent browser context](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)
- [Playwright authentication](https://playwright.dev/python/docs/auth)
- [Playwright existing-browser connection](https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp)
- [Chrome debugging connection configuration](https://developer.chrome.com/docs/devtools/agents/get-started/configuration/)
- [Meta automated collection context](https://about.fb.com/news/2021/04/how-we-combat-scraping/)
