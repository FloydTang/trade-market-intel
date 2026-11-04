#!/usr/bin/env python3
"""Export one reviewed market route; never calls a service or changes a CRM."""
import argparse
import hashlib
import json
from pathlib import Path
from build_market_report import build, require


def export(data, series_id, market, selected_by, max_results=6):
    require(isinstance(selected_by, str) and selected_by.strip(), 'selected_by is required')
    require(type(max_results) is int and 1 <= max_results <= 20, 'max_results must be 1..20')
    report, _, bridges = build(data)
    matches = [b for b in bridges if b['research_series_id'] == series_id and b['target_market'] == market]
    require(len(matches) == 1, 'select exactly one eligible market/series for the actual seller role')
    bridge = matches[0]
    scope = report['scopes'][bridge['research_scope_id']]
    context = {
        'contract_version': '1.0', 'synthetic': report['synthetic'],
        'selected_by': selected_by.strip(), 'series_id': series_id,
        'scope': scope, 'seller_role': data['seller_role'],
        'market': market, 'tier': bridge['market_tier'],
        'sources': report['sources'], 'claims': report['claims'],
        'collection_errors': report['collection_errors'],
        'decision': next(d for d in report['decisions'] if d['series_id'] == series_id
                         and d['market'] == market and d['seller_role'] == data['seller_role']),
        'status': 'selected_for_discovery_only',
        'company_claims_authorized': False, 'outreach_authorized': False,
        'downstream_rule': 'Market context is not evidence about a particular buyer. Reverify facts and approve sales angles separately.',
    }
    discovery = {k: bridge[k] for k in ('product_or_offer', 'target_market', 'customer_type',
                                       'industry_lens', 'seller_context', 'search_keywords', 'exclude_terms')}
    require(bool(discovery['search_keywords']), 'at least one search keyword required')
    # Existing discovery normalizer preserves notes, but discards unknown fields.
    discovery.update(must_include=[], max_results=max_results, data_sources=[],
                     notes=('SYNTHETIC DEMO; ' if report['synthetic'] else '') +
                     'Market research context: market-context.json; series=' + series_id +
                     '; role=' + data['seller_role'] + '; tier=' + bridge['market_tier'] +
                     '. Market evidence is not buyer intent; no outreach authorization.')
    return discovery, context


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-json', required=True, type=Path)
    p.add_argument('--series-id', required=True)
    p.add_argument('--market', required=True)
    p.add_argument('--selected-by', required=True, help='Operator identifier recording the actual market selection')
    p.add_argument('--max-results', type=int, default=6)
    p.add_argument('--news-context', type=Path, help='Optional collect_news_context.py output, treated only as unverified news')
    p.add_argument('--output-dir', required=True, type=Path)
    args = p.parse_args()
    original = args.input_json.read_bytes()
    discovery, context = export(json.loads(original), args.series_id, args.market,
                                args.selected_by, args.max_results)
    context['input_sha256'] = hashlib.sha256(original).hexdigest()
    if args.news_context:
        news = json.loads(args.news_context.read_text(encoding='utf-8'))
        require(isinstance(news, dict) and news.get('contract_version') == '1.0'
                and news.get('status') in ('ok', 'no_matches', 'unavailable')
                and isinstance(news.get('signals'), list), 'invalid news context')
        context['news_context'] = news
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in (('lead-discovery-input.json', discovery), ('market-context.json', context)):
        (args.output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Exported selected route; no search, API call, database write, or outreach executed.')


if __name__ == '__main__':
    main()
