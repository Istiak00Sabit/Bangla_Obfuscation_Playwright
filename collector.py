#!/usr/bin/env python3
"""Facebook rendered-text collector with manual login and open-ended annotation.

All detected text is retained; signals never filter ingestion. Read-only UI
expansion, ordinary scrolling, no stealth/proxy/CAPTCHA bypass or posting.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from signals import ANNOTATION_TYPES, analyze

BD_PUBLIC_PAGES = (
    'https://www.facebook.com/DailyProthomAlo',
    'https://www.facebook.com/JamunaTelevision',
    'https://www.facebook.com/bcbtigercricket',
    'https://www.facebook.com/channelitv',
)

ROOT = Path(__file__).resolve().parent
EXTRACT_JS = (ROOT / 'extract.js').read_text(encoding='utf-8')
READ_MORE = re.compile(
    r'^(?:see more|see more comments|view (?:more|previous) comments|'
    r'view (?:[\d,]+ )?(?:more )?(?:comments|replies)|more comments|'
    r'আরও দেখুন|আরো দেখুন|আরও মন্তব্য দেখুন|আরো মন্তব্য দেখুন|'
    r'আরও উত্তর দেখুন|আগের মন্তব্যগুলো দেখুন|'
    r'আরও [০-৯\d,]+(?:টি)? (?:মন্তব্য|উত্তর)(?: দেখুন)?)$', re.I)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode('utf-8')).hexdigest()


def read_jsonl(path):
    if path.exists():
        with path.open(encoding='utf-8') as f:
            for lineno, line in enumerate(f, 1):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as e:
                        raise ValueError(f'{path}:{lineno}: invalid JSON; keep/repair the file before resuming') from e


def append_json(path, row):
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')


def atomic_jsonl(path, rows):
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    tmp.replace(path)


def spreadsheet_cell(value):
    value = '' if value is None else str(value)
    # JSONL is the unmodified research source. CSV is spreadsheet-safe.
    if value.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r')):
        return "'" + value
    return value


class Dataset:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.records = {r['record_id']: r for r in read_jsonl(self.directory / 'records.jsonl')}
        self.media = {r['media_id']: r for r in read_jsonl(self.directory / 'media.jsonl')}
        self.crawl_id = uuid.uuid4().hex

    def ingest(self, batch, source_url, page_url):
        additions = 0
        for row in batch['records']:
            raw = row['raw_text']
            identity_url = row.get('item_url', '')
            parsed = urlparse(identity_url)
            is_comment_link = any(k in parse_qs(parsed.query) for k in ('comment_id', 'reply_comment_id'))
            # A post URL must not merge many comments. Distinct fallback DOM nodes
            # remain separate even when two users write the same comment.
            stable = identity_url if identity_url and (row['kind'] != 'comment' or is_comment_link) else ''
            identity = f"{stable}:slot:{row.get('message_slot', 0)}" if stable else f"{self.crawl_id}:{row['dom_node_key']}"
            rid = digest(source_url, row['kind'], identity)
            old = self.records.get(rid)
            analysis = analyze(raw)
            if old and old['raw_text'] == raw:
                for name in ('human_label', 'normalized_text', 'confirmed_types', 'annotation_notes'):
                    analysis[name] = old.get('analysis', {}).get(name, analysis[name])
            row = dict(row, record_id=rid, crawl_id=self.crawl_id, source_url=source_url,
                       page_url=page_url, captured_at_utc=old['captured_at_utc'] if old else now(),
                       last_seen_at_utc=now(), content_hash=digest(raw), analysis=analysis)
            if old and old['raw_text'] != raw:
                append_json(self.directory / 'revisions.jsonl', old)
            self.records[rid] = row
            additions += old is None or old['raw_text'] != raw
        for row in batch.get('images', []):
            mid = digest(source_url, row['image_url'])
            self.media[mid] = dict(row, media_id=mid, source_url=source_url,
                                   captured_at_utc=self.media.get(mid, {}).get('captured_at_utc', now()))
        return additions

    def save(self):
        atomic_jsonl(self.directory / 'records.jsonl', self.records.values())
        atomic_jsonl(self.directory / 'media.jsonl', self.media.values())

    def export(self):
        self.save()
        fields = ['record_id', 'kind', 'raw_text', 'visible_text', 'context_text', 'source_url',
                  'item_url', 'captured_at_utc', 'extraction_method', 'content_hash',
                  'signal_names', 'human_label', 'normalized_text', 'confirmed_types', 'annotation_notes']
        counts = {}
        for r in self.records.values():
            counts[r['content_hash']] = counts.get(r['content_hash'], 0) + 1
        for name, only_signals in [('all_records.csv', False), ('surface_candidates.csv', True)]:
            with (self.directory / name).open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                for r in self.records.values():
                    a = r['analysis']
                    if only_signals and not a['has_surface_signals']:
                        continue
                    row = {k: r.get(k, '') for k in fields}
                    row.update({k: a.get(k, '') for k in ['human_label', 'normalized_text', 'annotation_notes']})
                    row['confirmed_types'] = '|'.join(a.get('confirmed_types', []))
                    row['signal_names'] = '|'.join(sorted({s['signal'] for s in a['signals']}))
                    writer.writerow({k: spreadsheet_cell(v) for k, v in row.items()})
        summary = {
            'exported_at_utc': now(), 'records': len(self.records), 'media_to_review': len(self.media),
            'records_with_surface_signals': sum(r['analysis']['has_surface_signals'] for r in self.records.values()),
            'repeated_exact_text_groups': sum(v > 1 for v in counts.values()),
            'all_obfuscation_types_found': 'NOT CLAIMED: unknown and semantic types need human review',
            'raw_text_source': 'records.jsonl; no Unicode normalization applied',
        }
        (self.directory / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        (self.directory / 'annotation_types.json').write_text(json.dumps(ANNOTATION_TYPES, ensure_ascii=False, indent=2), encoding='utf-8')
        return summary


def is_facebook_url(url):
    p = urlparse(url)
    host = (p.hostname or '').lower()
    return p.scheme == 'https' and (host == 'facebook.com' or host.endswith('.facebook.com'))


def blocking_reason(page):
    path = urlparse(page.url).path.lower()
    if any(part in path for part in ('/checkpoint', '/login', '/recover', '/two_step_verification')):
        return 'Login/checkpoint requires manual action; run the login command.'
    if page.locator('input[type="password"]:visible, iframe[src*="captcha"]:visible, '
                    '[id*="captcha"]:visible').count():
        return 'A login or CAPTCHA is visible; manual action required.'
    return ''


def expand_read_controls(page, budget):
    clicked = 0
    # Exact, allowlisted read/expand labels only. No Like/Share/Reply/send actions.
    for _ in range(budget):
        match = page.get_by_role('button', name=READ_MORE)
        did_click = False
        for i in range(min(match.count(), 60)):
            button = match.nth(i)
            try:
                if button.is_visible():
                    button.click(timeout=1200)
                    page.wait_for_timeout(300)
                    clicked += 1
                    did_click = True
                    break
            except Exception:
                continue
        if not did_click:
            break
    return clicked


def select_all_comments(page):
    opened = False
    menus = re.compile(r'^(?:Most relevant|Newest|Top comments|সবচেয়ে প্রাসঙ্গিক|সবচেয়ে প্রাসঙ্গিক|নতুনগুলো)$', re.I)
    try:
        switches = page.get_by_role('button', name=menus)
        for i in range(min(switches.count(), 20)):
            if switches.nth(i).is_visible():
                switches.nth(i).click(timeout=1500)
                opened = True
                break
        if not opened:
            return False
        choice = re.compile(r'^(?:All comments|সব মন্তব্য|সমস্ত মন্তব্য)$', re.I)
        for role in ('menuitem', 'option', 'button'):
            candidates = page.get_by_role(role, name=choice)
            for i in range(candidates.count()):
                if candidates.nth(i).is_visible():
                    candidates.nth(i).click(timeout=1500)
                    page.wait_for_timeout(500)
                    return True
        page.keyboard.press('Escape')
    except Exception:
        if opened:
            page.keyboard.press('Escape')
    return False


SCROLL_JS = """() => {
 const dialog = [...document.querySelectorAll('[role="dialog"]')]
   .find(n => n.getClientRects().length);
 if (dialog) {
   const areas = [dialog, ...dialog.querySelectorAll('*')].filter(n => {
     const s = getComputedStyle(n);
     return n.clientHeight > 100 && n.scrollHeight > n.clientHeight + 30 &&
       /auto|scroll/.test(s.overflowY) && n.getClientRects().length;
   }).sort((a,b) => b.clientHeight-a.clientHeight);
   if (areas.length) {
     const n=areas[0], before=n.scrollTop;
     n.scrollBy(0, Math.max(300, n.clientHeight*0.8));
     return {container:'dialog', moved:n.scrollTop!==before};
   }
 }
 const before=window.scrollY;
 window.scrollBy(0, Math.max(400, innerHeight*0.8));
 return {container:'window', moved:window.scrollY!==before};
}"""


def browser_options(args, persistent=True):
    options = {'headless': getattr(args, 'headless', False)}
    if persistent:
        options['viewport'] = {'width': 1360, 'height': 900}
    if args.browser_executable:
        options['executable_path'] = args.browser_executable
    return options


def remember_post_links(snapshot, links, limit):
    for row in snapshot['records']:
        if len(links) >= limit:
            break
        url = row.get('item_url', '')
        if row['kind'] != 'post' or not is_facebook_url(url):
            continue
        parsed = urlparse(url)
        if '/posts/' in parsed.path or '/videos/' in parsed.path or '/permalink/' in parsed.path:
            links.setdefault(parsed._replace(query='', fragment='').geturl(), None)
        elif 'story_fbid' in parse_qs(parsed.query):
            links.setdefault(parsed._replace(fragment='').geturl(), None)


def collect_page(page, source_url, dataset, args, fixture=False, post_links=None):
    log = {'source_url': source_url, 'started_at_utc': now(), 'rounds': 0, 'status': 'running'}
    try:
        response = page.goto(source_url, wait_until='domcontentloaded', timeout=45000)
        if response and response.status in (401, 403, 429):
            log.update(status='blocked', reason=f'HTTP {response.status}')
            return log
        page.wait_for_timeout(int(args.wait * 1000))
        if args.manual and not args.headless:
            input('Browser ready. Select All comments/expand any needed threads, then press Enter here: ')
        reason = blocking_reason(page) if not fixture else ''
        if reason:
            log.update(status='manual_action_required', reason=reason)
            return log
        log['all_comments_selected'] = select_all_comments(page)
        idle = 0
        for n in range(args.max_rounds):
            reason = blocking_reason(page) if not fixture else ''
            if reason:
                log.update(status='manual_action_required', reason=reason)
                break
            # Save before expanding/scrolling: Facebook can unmount earlier posts.
            before = page.evaluate(EXTRACT_JS)
            added = dataset.ingest(before, source_url, page.url)
            clicks = expand_read_controls(page, args.expand_budget)
            after = page.evaluate(EXTRACT_JS)
            added += dataset.ingest(after, source_url, page.url)
            if post_links is not None:
                remember_post_links(before, post_links, args.posts_per_page)
                remember_post_links(after, post_links, args.posts_per_page)
            dataset.save()
            log.update(rounds=n + 1, last_article_count=after['article_count'],
                       last_message_count=after['message_count'])
            print(f"  Round {n + 1}: {len(dataset.records)} retained records; {clicks} expansions", flush=True)
            idle = idle + 1 if added == 0 and clicks == 0 else 0
            if idle >= args.idle_rounds:
                log.update(status='finished_visible_content', reason='No new content after idle rounds')
                break
            if len(dataset.records) >= args.max_records:
                log.update(status='record_limit', reason='Configured dataset record limit reached')
                break
            page.evaluate(SCROLL_JS)
            page.wait_for_timeout(int(args.wait * 1000))
        else:
            log.update(status='round_limit', reason='Configured per-source round limit reached')
    except KeyboardInterrupt:
        log.update(status='interrupted')
        raise
    except Exception as e:
        log.update(status='error', reason=f'{type(e).__name__}: {str(e)[:500]}')
        print(log['reason'], file=sys.stderr)
    finally:
        log['ended_at_utc'] = now()
        append_json(dataset.directory / 'crawl_log.jsonl', log)
    return log


@contextmanager
def collection_page(pw, args):
    """Use an approved existing Chrome connection or our separate browser profile.

    Attached mode owns one new tab only. It never launches Chrome against the
    user's existing data directory or closes their browser/context/other tabs.
    """
    if args.attach_chrome:
        if args.headless:
            raise ValueError('--attach-chrome uses the visible running Chrome; remove --headless')
        print('Connecting to your running Google Chrome. Approve Chrome\'s connection prompt if shown.', flush=True)
        try:
            browser = pw.chromium.connect_over_cdp('chrome', no_defaults=True, timeout=60000)
        except Exception as e:
            raise RuntimeError(
                'Could not attach to Chrome. In your installed Chrome open '
                'chrome://inspect/#remote-debugging, enable remote debugging and '
                'approve the connection prompt. Keep Chrome open. Update the '
                'Python package with: python -m pip install -r requirements.txt. '
                'If that setting is unavailable, use the separate-profile login mode. '
                f'Connection details: {e}'
            ) from e
        if not browser.contexts:
            raise RuntimeError('Chrome did not expose its existing browser context.')
        page = browser.contexts[0].new_page()
        try:
            yield page
        finally:
            if not page.is_closed():
                page.close()
            # Stopping Playwright disconnects the client. Do not close the
            # user's Browser or BrowserContext explicitly.
    else:
        with pw.chromium.launch_persistent_context(str(Path(args.profile).resolve()), **browser_options(args)) as context:
            yield context.pages[0] if context.pages else context.new_page()


def collect(args):
    urls = list(BD_PUBLIC_PAGES if args.bd_public_pages else ())
    urls.extend(args.url or [])
    if args.urls:
        urls += [s.strip() for s in Path(args.urls).read_text(encoding='utf-8-sig').splitlines()
                 if s.strip() and not s.lstrip().startswith('#')]
    urls = list(dict.fromkeys(urls))
    if not urls:
        raise ValueError('Add Facebook URLs to urls.txt or pass --url https://www.facebook.com/...')
    if any(not is_facebook_url(url) for url in urls):
        raise ValueError('collect accepts HTTPS facebook.com URLs only; demo uses a separate local fixture')
    if args.manual and args.headless:
        raise ValueError('--manual needs a visible browser; remove --headless')
    from playwright.sync_api import sync_playwright
    dataset = Dataset(args.output)
    status = 0
    try:
        with sync_playwright() as pw:
            with collection_page(pw, args) as page:
                page.set_default_timeout(4000)
                page.on('dialog', lambda d: d.dismiss())
                pending = [(url, args.bd_public_pages and url in BD_PUBLIC_PAGES) for url in urls]
                scheduled = set(urls)
                cursor = 0
                while cursor < len(pending):
                    url, discover = pending[cursor]
                    cursor += 1
                    if len(dataset.records) >= args.max_records:
                        print('Dataset limit already reached; increase --max-records to continue.')
                        break
                    print(f'Collecting: {url}', flush=True)
                    post_links = {} if discover else None
                    result = collect_page(page, url, dataset, args, post_links=post_links)
                    for post_url in post_links or ():
                        if post_url not in scheduled:
                            scheduled.add(post_url)
                            pending.append((post_url, False))
                    if result['status'] in ('manual_action_required', 'blocked', 'error'):
                        print(result.get('reason', ''), file=sys.stderr)
                        status = 2
                        if result['status'] != 'error':
                            break
    except KeyboardInterrupt:
        status = 130
        print('Stopped. Saving collected text.')
    finally:
        summary = dataset.export()
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print('Review all_records.csv too: an empty signal list does NOT mean no obfuscation.')
    return status


def login(args):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        with pw.chromium.launch_persistent_context(str(Path(args.profile).resolve()), **browser_options(args)) as context:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto('https://www.facebook.com/', wait_until='domcontentloaded', timeout=45000)
            input('Log in yourself in this browser, finish any checks, then press Enter here to save and close: ')
    print('Browser profile saved locally. Run collect with the same --profile path.')
    return 0


def demo(args):
    """Entirely synthetic local content. Never contacts Facebook."""
    from playwright.sync_api import sync_playwright
    dataset = Dataset(args.output)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**browser_options(args, persistent=False))
        try:
            page = browser.new_page()
            collect_page(page, (ROOT / 'tests' / 'fixture.html').as_uri(), dataset, args, fixture=True)
        finally:
            browser.close()
    print(json.dumps(dataset.export(), ensure_ascii=False, indent=2))
    print('Synthetic demo only; not a Facebook dataset or live-site validation.')
    return 0


def import_review(args):
    dataset = Dataset(args.output)
    updates = []
    with Path(args.csv).open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            rid = row.get('record_id', '')
            if rid not in dataset.records:
                raise ValueError(f'Unknown record_id: {rid}')
            record = dataset.records[rid]
            if row.get('raw_text') != spreadsheet_cell(record['raw_text']):
                raise ValueError(f'raw_text changed for {rid}. Edit normalized_text, not raw_text.')
            label = row.get('human_label', '').strip()
            if label not in ('unreviewed', 'obfuscated', 'plain', 'uncertain'):
                raise ValueError(f'Invalid human_label: {label}')
            values = {'human_label': label,
                      'confirmed_types': [v.strip() for v in row.get('confirmed_types', '').split('|') if v.strip()]}
            for name in ('normalized_text', 'annotation_notes'):
                old = record['analysis'].get(name, '')
                incoming = row.get(name, '')
                values[name] = old if incoming == spreadsheet_cell(old) else incoming
            updates.append((rid, values))
    for rid, values in updates:
        dataset.records[rid]['analysis'].update(values)
    dataset.export()
    print(f'Imported {len(updates)} annotation rows; original raw_text was preserved.')
    return 0


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    for name in ('login', 'collect', 'demo'):
        c = sub.add_parser(name)
        c.add_argument('--profile', default=str(ROOT / '.browser-profile'))
        c.add_argument('--browser-executable', default=os.environ.get('COLLECTOR_BROWSER'))
        if name != 'login':
            c.add_argument('--headless', action='store_true', default=name == 'demo')
            c.add_argument('--output', default='demo_output' if name == 'demo' else 'data')
            c.add_argument('--wait', type=float, default=1.5)
            c.add_argument('--max-rounds', type=int, default=4 if name == 'demo' else 60)
            c.add_argument('--idle-rounds', type=int, default=3)
            c.add_argument('--max-records', type=int, default=10000)
            c.add_argument('--expand-budget', type=int, default=8)
            c.add_argument('--manual', action='store_true')
        if name == 'collect':
            c.add_argument('--bd-public-pages', action='store_true',
                           help='Scan selected Bangladeshi news, sport and entertainment pages')
            c.add_argument('--posts-per-page', type=int, choices=range(1, 21), default=4,
                           metavar='1..20', help='Open up to this many discovered posts per preset page')
            c.add_argument('--url', action='append')
            c.add_argument('--urls', help='UTF-8 file with one HTTPS Facebook URL per line')
            c.add_argument('--attach-chrome', action='store_true',
                           help='Connect to your running Google Chrome after you enable/approve remote debugging')
        c.set_defaults(func={'login': login, 'collect': collect, 'demo': demo}[name])
    e = sub.add_parser('export', help='Recreate CSVs from canonical records.jsonl')
    e.add_argument('--output', default='data')
    e.set_defaults(func=lambda a: print(json.dumps(Dataset(a.output).export(), indent=2)) or 0)
    a = sub.add_parser('import-review', help='Import manual labels from an edited copy of all_records.csv')
    a.add_argument('--csv', required=True)
    a.add_argument('--output', default='data')
    a.set_defaults(func=import_review)
    return p


def main():
    args = parser().parse_args()
    if hasattr(args, 'wait') and (args.wait < 0.2 or min(args.max_rounds, args.idle_rounds,
                                                     args.max_records, args.expand_budget) < 1):
        raise ValueError('wait must be >= 0.2 seconds and all limits must be positive')
    return args.func(args)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        print('Check installation, close another browser using the same profile, and review README_BN.md.', file=sys.stderr)
        sys.exit(1)
