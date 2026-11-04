#!/usr/bin/env python3
"""Offline MCP protocol tests, plus the real combo when --workflow-root is provided."""
import argparse
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from collect_mcp_context import collect, decode_response, MCPError
from run_market_outreach import ReplayClient

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = None


class MCPChecks(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((ROOT / 'examples/mcp-protocol-fixture.json').read_text())

    def test_json_and_sse_match_request_id(self):
        value = dict(jsonrpc='2.0', id=3, result=dict(tools=[]))
        self.assertEqual(decode_response(json.dumps(value).encode(), 3), dict(tools=[]))
        sse = ': keepalive\r\n\r\nevent: message\r\ndata: ' + json.dumps(value) + '\r\n\r\n'
        self.assertEqual(decode_response(sse.encode(), 3), dict(tools=[]))
        with self.assertRaises(MCPError):decode_response(json.dumps(value).encode(), 4)
        with self.assertRaises(MCPError):decode_response(b'{"jsonrpc":"2.0","id":3,"error":{"code":-1}}', 3)

    def test_mcp_initialize_discover_and_call(self):
        calls = []
        fixture = self.fixture
        class Client(ReplayClient):
            def exchange(self, method, params=None, notification=False):
                calls.append((method, params))
                return super().exchange(method, params, notification)
        result = collect('frozen vegetables', client=Client(fixture))
        self.assertEqual(result['status'], 'ok')
        self.assertEqual([m for m,p in calls], ['initialize', 'notifications/initialized', 'tools/list', 'tools/call'])
        self.assertEqual(result['tool'], 'waimaotong_search')
        self.assertEqual(result['signals'][0]['verification_status'], 'original_not_verified')

    def test_missing_tool_server_error_and_empty_are_distinct(self):
        for mutate in ('tool', 'server', 'isError', 'schema'):
            d = copy.deepcopy(self.fixture)
            if mutate == 'tool':d['tools/list']['tools'] = []
            if mutate == 'server':d['initialize']['serverInfo']['name'] = 'wrong-server'
            if mutate == 'isError':d['tools/call']['isError'] = True
            if mutate == 'schema':d['tools/call']['structuredContent'] = {}
            with self.subTest(mutate=mutate):
                result = collect('silk', client=ReplayClient(d))
                self.assertEqual(result['status'], 'unavailable')
                self.assertFalse(result['signals'])
        self.fixture['tools/call']['structuredContent']['items'] = []
        self.assertEqual(collect('silk', client=ReplayClient(self.fixture))['status'], 'no_matches')


class PipelineChecks(unittest.TestCase):
    def setUp(self):
        if WORKFLOW_ROOT is None:
            self.skipTest('provide --workflow-root for actual combo integration tests')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.config = json.loads((ROOT / 'examples/market-first-workflow.json').read_text())
        market = self.config['market_research']
        market['input_json'] = str(ROOT / 'examples' / market['input_json'])
        market['mcp']['fixture_json'] = str(ROOT / 'examples' / market['mcp']['fixture_json'])
        for section,key in (('lead_discovery','fixtures_json'),('customer_intel','report_json')):
            self.config['workflow'][section][key] = str(ROOT / 'examples' / self.config['workflow'][section][key])
        self.path = self.base / 'config.json'
        self.out = self.base / 'run'
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.config), encoding='utf-8')

    def call(self, *extra):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/run_market_outreach.py'), '--config', str(self.path),
                               '--workflow-root', str(WORKFLOW_ROOT), '--output-dir', str(self.out), *extra],
                              capture_output=True, text=True)

    def state(self):
        return json.loads((self.out / '00-market-pipeline-manifest.json').read_text())

    def select(self):
        return self.call('--resume', '--selected-series-id', 'food-import', '--selected-market', 'Poland',
                         '--selected-by', 'Synthetic regression operator')

    def test_full_chain_preserves_context_and_real_followup_gate(self):
        first = self.call()
        self.assertEqual(first.returncode, 10, first.stderr)
        self.assertEqual(self.state()['status'], 'awaiting_market_selection')
        self.assertFalse((self.out / 'outreach').exists())
        selected = self.select()
        self.assertEqual(selected.returncode, 10, selected.stderr)
        self.assertEqual(self.state()['status'], 'awaiting_sales_angle_approval')
        self.assertFalse((self.out / 'outreach/08-email-draft.json').exists())
        approved = self.call('--resume', '--approved-sales-angle-id', 'ANGLE-01', '--reviewer', 'Synthetic fixture reviewer')
        self.assertEqual(approved.returncode, 0, approved.stderr)
        for file, keys in [('05-selected-customer-intel-input.json',['market_research_context']),
                           ('06-customer-intel-report.json',['market_research_context']),
                           ('07-email-input.json',['source_context','market_research_context']),
                           ('08-email-draft.json',['source_context','market_research_context']),
                           ('09-container-bundle.json',['market_research_context'])]:
            d = json.loads((self.out / 'outreach' / file).read_text())
            for key in keys:d = d[key]
            self.assertEqual(d['market'], 'Poland')
            self.assertEqual(d['news_context']['transport'], 'mcp_fixture')
            self.assertFalse(d['outreach_authorized'])
        draft = json.loads((self.out / 'outreach/08-email-draft.json').read_text())
        self.assertEqual(draft['send_policy'], 'manual_review_only')
        self.assertEqual(self.call('--resume').returncode, 0)
        plan = json.loads((self.out / 'follow-up-plan.json').read_text())
        self.assertEqual(plan['status'], 'awaiting_actual_contact_record')
        self.assertIsNone(plan['previous_contact_context'])
        self.assertFalse(plan['auto_send'])
        follow = json.loads((self.out / 'follow-up-config.template.json').read_text())
        follow_path = self.base / 'follow.json'
        follow_path.write_text(json.dumps(follow))
        runner = WORKFLOW_ROOT / '主动开发链路组合包/scripts/run_workflow.py'
        command = [sys.executable, str(runner), '--config', str(follow_path), '--output-dir', str(self.base / 'follow-run')]
        missing = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)
        follow['outreach']['previous_contact_context'] = 'SYNTHETIC CONTACT RECORD: catalog sent; buyer replied asking for specifications.'
        follow_path.write_text(json.dumps(follow))
        waiting = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(waiting.returncode, 10, waiting.stderr)
        done = subprocess.run(command + ['--resume','--approved-sales-angle-id','ANGLE-01','--reviewer','Synthetic follow-up reviewer'], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        follow_input = json.loads((self.base / 'follow-run/07-email-input.json').read_text())
        self.assertEqual(follow_input['previous_contact_context'], follow['outreach']['previous_contact_context'])
        self.assertEqual(follow_input['source_context']['market_research_context']['market'], 'Poland')

    def test_market_tampering_and_wrong_role_selection_stop(self):
        self.assertEqual(self.call().returncode, 10)
        blocked = self.call('--resume','--selected-series-id','food-import','--selected-market','Missing market','--selected-by','Demo')
        self.assertEqual(blocked.returncode, 11)
        self.assertFalse((self.out / 'outreach').exists())
        news = self.out / 'market/market-news.json'
        news.write_text(news.read_text() + '\n')
        tampered = self.select()
        self.assertEqual(tampered.returncode, 2)
        self.assertFalse((self.out / 'outreach').exists())

    def test_mcp_failure_stops_before_search(self):
        fixture = json.loads((ROOT / 'examples/mcp-protocol-fixture.json').read_text())
        fixture['tools/call']['isError'] = True
        path = self.base / 'failed-mcp.json'
        path.write_text(json.dumps(fixture))
        self.config['market_research']['mcp']['fixture_json'] = str(path)
        self.save()
        result = self.call()
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(self.state()['status'], 'mcp_unavailable')
        self.assertFalse((self.out / 'outreach').exists())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workflow-root', type=Path)
    args, rest = parser.parse_known_args()
    WORKFLOW_ROOT = args.workflow_root.resolve() if args.workflow_root else None
    unittest.main(argv=[sys.argv[0], *rest])
