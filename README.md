# Bangla Obfuscation Playwright Collector

Research collector that retains all extracted text, including unseen/unknown
obfuscation patterns, with raw Unicode, context and source links. Surface
signals are candidates for human review, not automatic ground-truth labels.

**বাংলায় বিস্তারিত নির্দেশনা: [README_BN.md](README_BN.md).**

## Windows: existing logged-in Chrome

1. Clone this repository once. Copy `urls.example.txt` to `urls.txt` and add your Facebook post/page links.
2. In your logged-in Chrome profile, open `chrome://inspect/#remote-debugging`, enable remote debugging and keep Chrome open.
3. Run `RUN_WINDOWS.bat` and choose **4**. Approve Chrome's connection prompt if shown.

This mode connects through Playwright's supported existing-browser connection.
It does not copy/decrypt browser cookie files or download another Chromium.

For an existing Python environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe collector.py collect --urls urls.txt --attach-chrome
```

## Updates

Close the collector before updating, then run `UPDATE_WINDOWS.bat`, or:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`urls.txt`, collected `data/`, `.browser-profile/` and `.venv/` are local and ignored
by git. Store other runs/profiles outside the repository or add their chosen paths
to your local git excludes before committing. No user data or sessions are included.

## Output and review

- `data/records.jsonl`: canonical unnormalized extracted text and context.
- `data/all_records.csv`: review all text, including records without a signal.
- `data/surface_candidates.csv`: optional subset with surface signals.
- `data/media.jsonl`: image-link manifest; image OCR is not implemented.

Review a copy of `all_records.csv`, then import your annotations:

```powershell
.\.venv\Scripts\python.exe collector.py import-review --csv annotated.csv
```

## Validation and limits

18 non-browser tests passed. Two real-browser fixture tests could not run in
the creation host because Chromium could not open its required socket.
Existing-Chrome connection lifecycle is covered with mocks, not a real Windows
Chrome session. Facebook's changing UI may require selector adjustments.
This is not a claim of complete crawl coverage or complete obfuscation detection.

```bash
python -m unittest discover -s tests -v
```
