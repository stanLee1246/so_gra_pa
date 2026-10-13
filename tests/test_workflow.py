"""隔离临时数据，验证清洗与 API 口径；不改动默认演示数据库。"""
import contextlib
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient
import analysis
import app as web
import generate_demo
import prepare_data


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name)
        self.db = self.data / 'complaints.db'
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        for module in (analysis, generate_demo, prepare_data):
            self.stack.enter_context(patch.object(module, 'DATA', self.data))
        for module in (analysis, prepare_data, web):
            self.stack.enter_context(patch.object(module, 'DB', self.db))
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        generate_demo.generate(per_year=40)
        prepare_data.prepare()
        self.client = TestClient(web.app)

    def test_cleaning_and_database_constraints(self):
        q = json.loads((self.data/'quality.json').read_text())
        self.assertEqual([q[k] for k in ('raw_rows','clean_rows','rejected_rows','duplicate_rows','unknown_category_rows')], [160,130,10,20,10])
        self.assertTrue(q['conservation_ok'])
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(con.execute('SELECT SUM(complaint_count) FROM ads_monthly').fetchone()[0], 130)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM complaints WHERE status='已办结' AND (resolved_date<complaint_date OR resolved_date>'2025-12-31')").fetchone()[0], 0)
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute('UPDATE complaints SET amount=-1')

    def test_reject_nonfinite_amount_and_invalid_resolution(self):
        raw = pd.read_csv(self.data/'raw_demo.csv')
        extras = raw.iloc[30:33].copy()
        extras['complaint_id'] = ['EXTRA-1','EXTRA-2','EXTRA-3']
        extras.loc[extras.index[0], 'amount'] = float('inf')
        extras.loc[extras.index[1], ['status','resolved_date']] = ['已办结','2022-01-01']
        extras.loc[extras.index[2], ['status','resolved_date']] = ['处理中','2025-01-01']
        pd.concat([raw, extras]).to_csv(self.data/'raw_demo.csv', index=False)
        report = prepare_data.prepare()
        self.assertEqual(report['rejected_rows'], 13)
        self.assertEqual(report['clean_rows'], 130)

    def test_conflicting_ids_preserve_previous_database(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        raw = pd.read_csv(self.data/'raw_demo.csv')
        conflict = raw.head(1).copy()
        conflict['amount'] += 1
        pd.concat([raw, conflict]).to_csv(self.data/'raw_demo.csv', index=False)
        with self.assertRaisesRegex(ValueError, '内容冲突'):
            prepare_data.prepare()
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)

    def test_reproducibility_and_scenario(self):
        before = (self.data/'raw_demo.csv').read_bytes()
        generate_demo.generate(per_year=40)
        self.assertEqual(before, (self.data/'raw_demo.csv').read_bytes())
        generate_demo.generate(per_year=40, scenario='promotion')
        self.assertNotEqual(before, (self.data/'raw_demo.csv').read_bytes())

    def test_filtered_aggregation_pagination_and_export(self):
        for params in ({}, {'year':2024,'platform':'演示平台A','category':'食品'}, {'category':'未知','issue_type':'退款退货'}):
            response = self.client.get('/api/dashboard', params=params)
            self.assertEqual(response.status_code, 200)
            m = response.json()['metrics']
            where, bindings = analysis.filter_clause(**params)
            with sqlite3.connect(self.db) as con:
                expected = con.execute('SELECT COUNT(*) FROM complaints'+where, bindings).fetchone()[0]
                groups = dict(con.execute('SELECT issue_type,COUNT(*) FROM complaints'+where+' GROUP BY issue_type', bindings))
            self.assertEqual(m['total'], expected)
            for key in ('annual','monthly','types','categories','matrix','platform_types','type_year'):
                self.assertEqual(sum(d['count'] for d in m[key]), expected)
            self.assertEqual({d['name']:d['count'] for d in m['types'] if d['count']}, groups)
            records = self.client.get('/api/records', params={**params,'page_size':100}).json()
            self.assertEqual(records['total'], expected)
            self.assertEqual(len(records['items']), min(100, expected))
            export = self.client.get('/api/export', params=params)
            self.assertTrue(export.content.startswith(b'\xef\xbb\xbf'))
            self.assertEqual(len(pd.read_csv(io.BytesIO(export.content))), expected)
            if expected:
                self.assertAlmostEqual(sum(d['share'] for d in m['types']), 1)
        first = self.client.get('/api/records', params={'page':1}).json()['items']
        second = self.client.get('/api/records', params={'page':2}).json()['items']
        self.assertFalse(set(d['complaint_id'] for d in first) & set(d['complaint_id'] for d in second))

    def test_invalid_filters_and_empty_database(self):
        for params in ({'year':2022},{'year':'abc'},{'platform':"' OR 1=1 --"},{'category':'不存在'},{'issue_type':'不存在'}):
            for path in ('/api/dashboard','/api/records','/api/export'):
                self.assertEqual(self.client.get(path, params=params).status_code, 422)
        for params in ({'page':0},{'page_size':0},{'page_size':101}):
            self.assertEqual(self.client.get('/api/records', params=params).status_code, 422)
        with sqlite3.connect(self.db) as con:
            con.execute('DELETE FROM complaints')
        m = self.client.get('/api/dashboard').json()['metrics']
        self.assertEqual(m['total'], 0)
        for key in ('closure_share','median_amount','closed_duration_median'):
            self.assertIsNone(m[key])
        self.assertEqual(self.client.get('/api/records').json()['items'], [])
        self.db.unlink()
        self.assertEqual(self.client.get('/api/meta').status_code, 503)
        self.assertEqual(self.client.get('/api/dashboard').status_code, 503)


if __name__ == '__main__':
    unittest.main()
