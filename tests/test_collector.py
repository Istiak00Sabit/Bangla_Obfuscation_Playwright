import argparse
import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from collector import (Dataset, EXTRACT_JS, blocking_reason, expand_read_controls,
                       import_review, is_facebook_url, spreadsheet_cell, collection_page, parser)
from signals import analyze


class SignalTests(unittest.TestCase):
    def names(self, text):
        return {s['signal'] for s in analyze(text)['signals']}

    def test_bengali_marks_before_slash(self):
        self.assertIn('internal_symbol_candidate', self.names('লা / থি'))
        self.assertIn('internal_symbol_candidate', self.names('চা*টে'))

    def test_spacing(self):
        self.assertIn('short_spaced_fragments_candidate', self.names('ছু রি'))

    def test_invisible_characters_preserve_offsets(self):
        text = 'খু\u200bন'
        signals = analyze(text)['signals']
        cf = next(s for s in signals if s['signal'] == 'format_character_present')
        self.assertEqual(text[cf['start']:cf['end']], '\u200b')
        self.assertEqual(cf['start'], 2)

    def test_numbers_mixed_scripts_and_emphasis(self):
        names = self.names('১কের banglaকথা heyyy 🙂')
        self.assertTrue({'number_letter_mixture', 'mixed_script_token',
                         'repeated_character_candidate', 'emoji_or_pictograph_present'} <= names)

    def test_plain_does_not_become_automatic_negative(self):
        result = analyze('স্বাভাবিক বাংলা বাক্য।')
        self.assertFalse(result['has_surface_signals'])
        self.assertEqual(result['human_label'], 'unreviewed')

    def test_csv_formula_protection(self):
        for s in ['=1+1', '\t=cmd', ' +1', '-2', '@x']:
            self.assertEqual(spreadsheet_cell(s), "'" + s)
        self.assertEqual(spreadsheet_cell('বাংলা'), 'বাংলা')

    def test_url_scope(self):
        self.assertTrue(is_facebook_url('https://www.facebook.com/a/posts/1'))
        self.assertFalse(is_facebook_url('https://facebook.com.evil.example/a'))
        self.assertFalse(is_facebook_url('https://evilfacebook.com/a'))
        self.assertFalse(is_facebook_url('http://facebook.com/a'))


class ExistingChromeTests(unittest.TestCase):
    def setUp(self):
        self.pw = Mock()
        self.browser = Mock()
        self.context = Mock()
        self.page = Mock()
        self.page.is_closed.return_value = False
        self.browser.contexts = [self.context]
        self.context.new_page.return_value = self.page
        self.pw.chromium.connect_over_cdp.return_value = self.browser
        self.args = argparse.Namespace(attach_chrome=True, headless=False)

    def test_attach_uses_a_new_tab_in_existing_context(self):
        with collection_page(self.pw, self.args) as page:
            self.assertIs(page, self.page)
        self.pw.chromium.connect_over_cdp.assert_called_once_with('chrome', no_defaults=True, timeout=60000)
        self.pw.chromium.launch_persistent_context.assert_not_called()
        self.page.close.assert_called_once()
        self.context.close.assert_not_called()
        self.browser.close.assert_not_called()

    def test_error_closes_own_tab_only(self):
        with self.assertRaisesRegex(RuntimeError, 'collection failed'):
            with collection_page(self.pw, self.args):
                raise RuntimeError('collection failed')
        self.page.close.assert_called_once()
        self.browser.close.assert_not_called()
        self.context.close.assert_not_called()

    def test_headless_attach_is_rejected(self):
        self.args.headless = True
        with self.assertRaises(ValueError):
            with collection_page(self.pw, self.args):
                pass
        self.pw.chromium.connect_over_cdp.assert_not_called()

    def test_connection_failure_explains_the_setting(self):
        self.pw.chromium.connect_over_cdp.side_effect = RuntimeError('not enabled')
        with self.assertRaisesRegex(RuntimeError, 'chrome://inspect/#remote-debugging'):
            with collection_page(self.pw, self.args):
                pass
        self.context.new_page.assert_not_called()

    def test_cli_accepts_attach_mode(self):
        args = parser().parse_args(['collect', '--urls', 'urls.txt', '--attach-chrome'])
        self.assertTrue(args.attach_chrome)
        self.assertFalse(args.headless)


class DatasetTests(unittest.TestCase):
    def row(self, raw, node='1', kind='comment', url=''):
        return {'raw_text': raw, 'visible_text': raw, 'kind': kind, 'dom_node_key': node,
                'item_url': url, 'context_text': raw, 'extraction_method': 'message_node_text_content'}

    def test_plain_and_opaque_unknown_are_always_retained(self):
        with tempfile.TemporaryDirectory() as d:
            ds = Dataset(d)
            ds.ingest({'records': [self.row('স্বাভাবিক বাংলা বাক্য।'), self.row('অজানা সংকেত', '2')]}, 'source', 'page')
            ds.export()
            self.assertEqual(len(ds.records), 2)
            self.assertEqual(len(Dataset(d).records), 2)

    def test_distinct_equal_comments_are_not_deleted(self):
        with tempfile.TemporaryDirectory() as d:
            ds = Dataset(d)
            batch = {'records': [self.row('একই', '1'), self.row('একই', '2')]}
            ds.ingest(batch, 'source', 'page')
            ds.ingest(batch, 'source', 'page')
            self.assertEqual(len(ds.records), 2)

    def test_expansion_revises_record_without_loss(self):
        with tempfile.TemporaryDirectory() as d:
            ds = Dataset(d)
            ds.ingest({'records': [self.row('আংশিক')]}, 'source', 'page')
            ds.ingest({'records': [self.row('সম্পূর্ণ')]}, 'source', 'page')
            self.assertEqual(len(ds.records), 1)
            self.assertIn('আংশিক', Path(d, 'revisions.jsonl').read_text())

    def test_jsonl_roundtrip_exact_unicode_and_csv_safe(self):
        with tempfile.TemporaryDirectory() as d:
            ds = Dataset(d)
            raw = '  খু\u200bন\u200c\u200d\u00a0\n'
            ds.ingest({'records': [self.row(raw), self.row('=1+1', '2')]}, 'source', 'page')
            ds.export()
            reread = Dataset(d)
            self.assertEqual(next(iter(reread.records.values()))['raw_text'], raw)
            with Path(d, 'all_records.csv').open(encoding='utf-8-sig', newline='') as f:
                csv_rows = list(csv.DictReader(f))
            self.assertEqual(csv_rows[1]['raw_text'], "'=1+1")
            self.assertEqual(list(reread.records.values())[1]['raw_text'], '=1+1')

    def test_manual_review_import_preserves_source(self):
        with tempfile.TemporaryDirectory() as d:
            ds = Dataset(d)
            ds.ingest({'records': [self.row('খু\u200bন')]}, 'source', 'page')
            ds.export()
            src = Path(d, 'all_records.csv')
            with src.open(encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                fields, rows = reader.fieldnames, list(reader)
            rows[0].update(human_label='obfuscated', normalized_text='খুন', confirmed_types='zero_width_format_manipulation|my_new_type')
            annotated = Path(d, 'annotated.csv')
            with annotated.open('w', encoding='utf-8-sig', newline='') as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                w.writerows(rows)
            import_review(argparse.Namespace(output=d, csv=str(annotated)))
            record = next(iter(Dataset(d).records.values()))
            self.assertEqual(record['raw_text'], 'খু\u200bন')
            self.assertEqual(record['analysis']['normalized_text'], 'খুন')
            self.assertIn('my_new_type', record['analysis']['confirmed_types'])

    def test_checkpoint_is_reported(self):
        page = Mock(url='https://www.facebook.com/checkpoint/123')
        self.assertTrue(blocking_reason(page))


@unittest.skipIf(os.environ.get('COLLECTOR_SKIP_BROWSER') == '1', 'Browser tests explicitly disabled by this host')
class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        options = {'headless': True}
        if os.environ.get('COLLECTOR_BROWSER'):
            options['executable_path'] = os.environ['COLLECTOR_BROWSER']
        cls.browser = cls.pw.chromium.launch(**options)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.set_content(Path('tests/fixture.html').read_text(encoding='utf-8'))

    def tearDown(self):
        self.page.close()

    def test_raw_unicode_and_plain_text_and_nested_comments(self):
        batch = self.page.evaluate(EXTRACT_JS)
        texts = [r['raw_text'] for r in batch['records']]
        self.assertIn('স্বাভাবিক বাংলা বাক্য।', texts)
        self.assertIn('খু\u200bন', texts)
        self.assertIn('  \u00a0খু\u200dন\u200c  ', texts)
        self.assertNotIn('HIDDEN_NOT_A_RECORD', texts)
        post = next(r for r in batch['records'] if r['raw_text'] == 'তিনি লা / থি দিয়েছেন।')
        self.assertEqual(post['kind'], 'post')
        self.assertEqual(sum(r['raw_text'] == 'একই মন্তব্য' for r in batch['records']), 2)
        self.assertTrue(any(r['extraction_method'] == 'article_fallback_with_ui' for r in batch['records']))

    def test_expand_updates_text_but_never_clicks_reply(self):
        self.assertEqual(expand_read_controls(self.page, 3), 1)
        batch = self.page.evaluate(EXTRACT_JS)
        self.assertIn('সম্পূর্ণ লেখা ছু রি', [r['raw_text'] for r in batch['records']])
        self.assertIsNone(self.page.evaluate('document.body.dataset.writeAction'))


if __name__ == '__main__':
    unittest.main()
