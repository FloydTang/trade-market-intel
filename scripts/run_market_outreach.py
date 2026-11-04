#!/usr/bin/env python3
"""Market-first entrypoint delegating discovery through follow-up drafts to the existing combo."""
import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
from build_market_report import require
from export_handoff import export
from collect_mcp_context import collect

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(value, dict), 'expected JSON object')
    return value


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve(base, value):
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


class ReplayClient:
    """Explicitly synthetic, offline JSON-RPC replay; never masquerades as a live MCP call."""
    def __init__(self, payload):
        self.payload = payload
        self.protocol = None

    def exchange(self, method, params=None, notification=False):
        return {} if notification else self.payload[method]


def run(args):
    config_path = args.config.resolve()
    config = read(config_path)
    output = args.output_dir.resolve()
    combo_root = args.workflow_root.resolve()
    runner = combo_root / '主动开发链路组合包/scripts/run_workflow.py'
    require(runner.is_file(), 'workflow-root must contain the existing active-outreach combo')
    require('market_context' in runner.read_text(encoding='utf-8'), 'update the combo to a market_context-compatible version')
    require(config.get('contract_version') == '1.0', 'contract_version must be 1.0')
    market = config.get('market_research')
    require(isinstance(market, dict), 'market_research is required')
    workflow = config.get('workflow')
    require(isinstance(workflow, dict) and workflow.get('start_mode') == 'discovery', 'workflow must start at discovery')
    require(not any(k in workflow.get('lead_discovery', {}) for k in ('input', 'input_json')),
            'discovery input is generated from the selected market; omit input/input_json')
    require(not any(k in workflow for k in ('market_context',)), 'market context must come from research')
    source = resolve(config_path.parent, market['input_json'])
    mcp = market.get('mcp', {})
    require(isinstance(mcp, dict) and mcp.get('mode', 'live') in ('live', 'fixture'), 'MCP mode must be live or fixture')
    query = mcp.get('query')
    require(isinstance(query, str) and 2 <= len(query.strip()) <= 200, 'MCP query is required (2..200 characters)')
    state_path = output / '00-market-pipeline-manifest.json'
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if args.resume:
        state = read(state_path)
        require(state['config_sha256'] == config_hash, 'pipeline config changed; start a new run')
        require(state['workflow_root'] == str(combo_root), 'workflow-root changed')
        require(state['workflow_runner_sha256'] == digest(runner), 'workflow runner changed; start a new run')
        require(state['source_sha256'] == digest(source), 'market evidence source changed')
        for path, expected in state['artifact_sha256'].items():
            require((output / path).is_file() and digest(output / path) == expected, 'registered market artifact changed: ' + path)
    else:
        require(not (args.approved_sales_angle_id or args.approval_json), 'sales approval is accepted only on resume after review')
        require(not output.exists() or not any(output.iterdir()), 'fresh run requires an empty output directory')
        output.mkdir(parents=True, exist_ok=True)
        state = dict(contract_version='1.0', config_sha256=config_hash, workflow_root=str(combo_root),
                     workflow_runner_sha256=digest(runner), source_sha256=digest(source), artifact_sha256={}, stages={}, status='running')
        write(output / '00-market-pipeline-config.json', config)
        write(output / '00-market-input.json', read(source))

    def register(path):
        state['artifact_sha256'][str(path.relative_to(output))] = digest(path)

    def save(status, code, next_action):
        state.update(status=status, exit_code=code, next_action=next_action,
                     updated_at=datetime.now(timezone.utc).isoformat())
        write(state_path, state)
        print(json.dumps(dict(status=status, manifest=str(state_path)), ensure_ascii=False))
        return code

    register(output / '00-market-pipeline-config.json')
    register(output / '00-market-input.json')
    evidence = read(output / '00-market-input.json')
    news_path = output / 'market/market-news.json'
    if not state['stages'].get('mcp'):
        client = None
        if mcp.get('mode', 'live') == 'fixture':
            require(evidence.get('synthetic') is True, 'MCP replay is only allowed for synthetic research')
            fixture_path = resolve(config_path.parent, mcp['fixture_json'])
            fixture = read(fixture_path)
            if 'mcp_fixture_sha256' in state:
                require(state['mcp_fixture_sha256'] == digest(fixture_path), 'MCP fixture changed')
            state['mcp_fixture_sha256'] = digest(fixture_path)
            client = ReplayClient(fixture)
        news = collect(query, mcp.get('limit', 10), client=client)
        if client:
            news.update(transport='mcp_fixture', synthetic=True)
        write(news_path, news)
        register(news_path)
        if news['status'] == 'unavailable':
            return save('mcp_unavailable', 3, 'Restore the read-only MCP connection and resume; discovery has not run.')
        state['stages']['mcp'] = dict(status=news['status'], transport=news['transport'])
        write(state_path, state)

    if not state['stages'].get('market_research'):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/build_market_report.py'),
                                 '--input-json', str(output / '00-market-input.json'),
                                 '--output-dir', str(output / 'market')], capture_output=True, text=True)
        if result.returncode:
            state['error'] = result.stderr[-2000:]
            return save('market_research_failed', 3, 'Correct the evidence input and start a new run.')
        for path in (output / 'market').iterdir():
            if path.is_file():
                register(path)
        state['stages']['market_research'] = dict(status='completed')

    generated = output / 'workflow.json'
    if not generated.exists():
        selection = market.get('selection', {})
        series = args.selected_series_id or selection.get('series_id')
        country = args.selected_market or selection.get('market')
        operator = args.selected_by or selection.get('selected_by')
        if not (series and country and operator):
            return save('awaiting_market_selection', 10, 'Review market/report.md, then resume with selected-series-id, selected-market and selected-by.')
        try:
            discovery, context = export(evidence, series, country, operator)
        except ValueError as error:
            state['error'] = str(error)
            return save('market_selection_hold', 11, 'Select an eligible route for the actual seller role; no discovery executed.')
        context.update(input_sha256=state['source_sha256'], news_context=read(news_path))
        write(output / 'market/lead-discovery-input.json', discovery)
        write(output / 'market/market-context.json', context)
        downstream = copy.deepcopy(workflow)
        downstream['market_context'] = context
        downstream['lead_discovery']['input'] = discovery
        for section in ('lead_discovery', 'customer_intel'):
            for key in ('fixtures_json', 'evidence_json', 'input_json', 'report_json'):
                if key in downstream[section]:
                    downstream[section][key] = str(resolve(config_path.parent, downstream[section][key]))
        write(generated, downstream)
        for path in (output / 'market/lead-discovery-input.json', output / 'market/market-context.json', generated):
            register(path)
        state['selection'] = dict(series_id=series, market=country, selected_by=operator)
        state['stages']['market_selection'] = dict(status='selected_for_discovery_only')
    else:
        selection = state['selection']
        for supplied, key in ((args.selected_series_id, 'series_id'), (args.selected_market, 'market'), (args.selected_by, 'selected_by')):
            require(not supplied or supplied == selection[key], 'selection changed; start a new pipeline run')

    write(state_path, state)
    command = [sys.executable, str(runner), '--config', str(generated), '--output-dir', str(output / 'outreach')]
    if (output / 'outreach/00-run-manifest.json').exists():
        command.append('--resume')
    for flag, value in (('--approved-sales-angle-id', args.approved_sales_angle_id), ('--reviewer', args.reviewer), ('--approval-json', args.approval_json)):
        if value:
            if flag == '--approval-json':
                value = str(Path(value).expanduser().resolve())
            command.extend([flag, value])
    result = subprocess.run(command, capture_output=True, text=True)
    downstream_manifest = output / 'outreach/00-run-manifest.json'
    if not downstream_manifest.is_file():
        state['error'] = (result.stderr or result.stdout)[-2000:]
        return save('downstream_failed', result.returncode if result.returncode in (2, 3) else 3, 'Check combo configuration; no draft completion claimed.')
    downstream_state = read(downstream_manifest)
    state['stages']['outreach'] = dict(status=downstream_state['status'], manifest='outreach/00-run-manifest.json')
    if result.returncode:
        return save(downstream_state['status'], result.returncode, downstream_state['next_action'])
    require(downstream_state['status'] == 'completed', 'downstream did not complete')
    plan_path = output / 'follow-up-plan.json'
    if not plan_path.exists():
        report = read(output / 'outreach/06-customer-intel-report.json')
        for angle in report.get('sales_angles', []):
            angle['approval_status'] = 'proposed'
        write(output / 'follow-up-report.json', report)
        follow = dict(contract_version='1.0', run_id=workflow['run_id'] + '.follow-up', start_mode='customer_intel',
                      market_context=read(output / 'market/market-context.json'),
                      customer_intel=dict(mode='reviewed_report', report_json=str(output / 'follow-up-report.json')),
                      outreach=dict(workflow['outreach'], email_type='follow_up', previous_contact_context=''),
                      exports=dict(container_bundle=False, feishu_sandbox=False))
        write(output / 'follow-up-config.template.json', follow)
        write(plan_path, dict(status='awaiting_actual_contact_record', previous_contact_context=None,
                              source_draft='outreach/08-email-draft.json',
                              next_action='Copy the follow-up config outside this run, record the actual sent/reply context and reverify current facts; run combo in a new directory, then review the report-bound sales angle.',
                              required_fields=['actual contact or reply context', 'responsible operator', 'next review date'],
                              send_policy='manual_review_only', auto_send=False, contact_history_invented=False))
        for path in (plan_path, output / 'follow-up-report.json', output / 'follow-up-config.template.json'):
            register(path)
    return save('completed', 0, 'Review the draft; record actual contact before using the follow-up template. No message sent.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--workflow-root', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    p.add_argument('--resume', action='store_true')
    for name in ('selected-series-id', 'selected-market', 'selected-by', 'approved-sales-angle-id', 'reviewer', 'approval-json'):
        p.add_argument('--' + name, default='')
    args = p.parse_args()
    try:
        return run(args)
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
