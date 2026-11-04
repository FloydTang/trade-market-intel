#!/usr/bin/env python3
"""Offline annual trade normalization and reviewable market-discovery bridge."""
import argparse
import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

UNITS = {'USD': 1, 'thousand_usd': 1000, 'million_usd': 1000000}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0

def indexed(items, label):
    require(isinstance(items, list), label+' must be a list')
    result = {}
    for item in items:
        require(isinstance(item, dict) and isinstance(item.get('id'), str) and item['id'], label+' needs id')
        require(item['id'] not in result, 'duplicate '+label+' id')
        result[item['id']] = item
    return result

def build(data):
    require(isinstance(data, dict), 'input must be an object')
    require(type(data.get('synthetic', False)) is bool, 'synthetic must be boolean')
    for key in ('product_or_offer', 'industry_lens'):
        require(isinstance(data.get(key), str) and data[key], 'missing '+key)
    require(data.get('seller_role') in ('OEM', 'ODM', 'trader', 'brand'), 'invalid seller_role')
    require(isinstance(data.get('seller_context'), dict), 'seller_context must be object')
    top = data.get('top_n', 20)
    require(type(top) is int and top in (10, 20), 'top_n must be 10 or 20')
    floor = data.get('growth_base_min_usd', 1000000)
    require(number(floor), 'invalid growth base floor')
    sources = indexed(data.get('sources'), 'sources')
    for source in sources.values():
        url = urlparse(source.get('url', ''))
        require(url.scheme in ('https', 'http') and url.hostname and not url.username and not url.password, 'source needs public URL without credentials')
        require(all(isinstance(source.get(k), str) and source[k] for k in ('quality', 'redistribution', 'retrieved_at')), 'source metadata missing')
        datetime.fromisoformat(source['retrieved_at'].replace('Z', '+00:00'))
    scopes = indexed(data.get('scopes'), 'scopes')
    for scope in scopes.values():
        require(all(isinstance(scope.get(k), str) and scope[k] for k in ('description', 'hs_version')), 'scope metadata missing')
        require(isinstance(scope.get('codes'), list) and scope['codes'] and all(isinstance(c, str) and c.isdigit() for c in scope['codes']), 'scope needs string codes')
        require(len(set(scope['codes'])) == len(scope['codes']), 'duplicate scope code')
        require(not any(a != b and b.startswith(a) for a in scope['codes'] for b in scope['codes']), 'overlapping parent/child codes')
        require(isinstance(scope.get('limitations'), list), 'scope limitations required')
    series = indexed(data.get('series'), 'series')
    require(bool(series), 'at least one series required')
    raw = []; rankings = {}; observations = {}
    for sid, item in series.items():
        require(item.get('scope_id') in scopes, 'unknown scope')
        require(item.get('flow') in ('global_import', 'china_export'), 'invalid flow')
        require(item.get('coverage') in ('reported_available', 'listed_subset'), 'invalid coverage')
        require(all(isinstance(item.get(k), str) and item[k] for k in ('valuation', 'coverage_note')), 'missing series comparability metadata')
        base, year = item.get('base_year'), item.get('year')
        require(type(base) is int and type(year) is int and year == base+1, 'annual series needs consecutive integer years')
        require(isinstance(item.get('records'), list), 'records must be list')
        cells = {}; kinds = {}
        for record in item['records']:
            require(isinstance(record, dict), 'record must be object')
            market = record.get('market'); kind = record.get('market_kind')
            require(isinstance(market, str) and market, 'market required')
            require(kind in ('country', 'group', 'world', 'unspecified'), 'invalid market kind')
            require(market not in kinds or kinds[market] == kind, 'market kind changed across years')
            kinds[market] = kind
            require(type(record.get('year')) is int and record['year'] in (base, year), 'record outside annual window')
            require(record.get('source_id') in sources, 'unknown record source')
            require(record.get('unit') in UNITS and number(record.get('value')), 'invalid value or unit')
            require(type(record.get('anomaly', False)) is bool, 'anomaly must be boolean')
            require('quantity' not in record or number(record['quantity']), 'invalid quantity')
            require('quantity' not in record or bool(record.get('quantity_unit')), 'quantity unit required')
            key = (market, record['year'])
            require(key not in cells, 'duplicate market/year; resolve revisions before computing')
            normalized = dict(record, value_usd=record['value']*UNITS[record['unit']], series_id=sid)
            require(math.isfinite(normalized['value_usd']), 'normalized value overflow')
            cells[key] = normalized; raw.append(normalized)
        country = []; groups = []
        for market, kind in kinds.items():
            current = cells.get((market, year)); prior = cells.get((market, base))
            if current is None: continue
            now = current['value_usd']; before = prior['value_usd'] if prior else None
            growth_pct = (now-before)/before*100 if before else None
            require(growth_pct is None or math.isfinite(growth_pct), 'growth overflow')
            row = {'market': market, 'base_usd': before, 'current_usd': now, 'delta_usd': now-before if before is not None else None, 'growth_pct': growth_pct, 'base_status': 'missing_not_zero' if before is None else ('reported_zero' if before == 0 else 'reported'), 'evidence_ids': sorted({current['source_id']} | ({prior['source_id']} if prior else set())), 'anomaly': bool(current.get('anomaly') or (prior and prior.get('anomaly')))}
            if kind == 'country':
                country.append(row); observations[(sid, market)] = row
            else: groups.append(dict(row, market_kind=kind))
        size = sorted(country, key=lambda r: (-r['current_usd'], r['market']))
        delta = sorted((r for r in country if r['delta_usd'] is not None and r['delta_usd'] > 0), key=lambda r: (-r['delta_usd'], r['market']))
        growth = sorted((r for r in delta if r['base_usd'] >= floor and r['growth_pct'] is not None), key=lambda r: (-r['growth_pct'], r['market']))
        rankings[sid] = {'scope_id': item['scope_id'], 'flow': item['flow'], 'year': year, 'base_year': base, 'valuation': item['valuation'], 'coverage': item['coverage'], 'coverage_note': item['coverage_note'], 'growth_base_min_usd': floor, 'size': size[:top], 'positive_delta': delta[:top], 'positive_growth': growth[:top], 'eligible_counts': {'size': len(size), 'positive_delta': len(delta), 'positive_growth': len(growth)}, 'groups_not_in_country_ranking': groups, 'base_only_not_assumed_zero': sorted(m for m,k in kinds.items() if k=='country' and (m,base) in cells and (m,year) not in cells), 'current_missing_base': [r['market'] for r in size if r['base_status']=='missing_not_zero']}
    assessments = data.get('assessments', [])
    require(isinstance(assessments, list), 'assessments must be list')
    decisions=[]; bridges=[]; seen=set()
    for item in assessments:
        require(isinstance(item, dict), 'assessment must be object')
        sid, market = item.get('series_id'), item.get('market')
        role = item.get('seller_role', data['seller_role'])
        require(role in ('OEM', 'ODM', 'trader', 'brand'), 'invalid assessment role')
        require(type(item.get('anomaly', False)) is bool, 'anomaly must be boolean')
        require(sid in series and isinstance(market,str) and market, 'invalid assessment identity')
        require((sid,market,role) not in seen, 'duplicate assessment')
        seen.add((sid,market,role))
        states=[]
        for dimension in ('role_fit', 'buyer_evidence', 'landed_cost'):
            d=item.get(dimension,{})
            require(isinstance(d,dict) and d.get('status') in ('supported','unknown','adverse'), 'invalid assessment dimension')
            refs=d.get('evidence_ids',[])
            require(isinstance(refs,list) and all(ref in sources for ref in refs), 'invalid assessment evidence')
            require(d['status']=='unknown' or bool(refs), 'nonunknown assessment needs evidence')
            states.append(d['status'])
        row=observations.get((sid,market))
        tier='hold'
        if row and states[0]=='supported' and 'adverse' not in states:
            tier='A' if all(s=='supported' for s in states) else 'B'
        if item.get('anomaly') or (row and row['anomaly']):tier='watch'
        decisions.append(dict(item,seller_role=role,tier=tier,judgment_type='inference',review_status='draft'))
        if tier in ('A','B') and role == data['seller_role']:
            require(isinstance(item.get('customer_type'),str) and item['customer_type'], 'bridge needs customer_type')
            for key in ('search_keywords','exclude_terms'):
                require(isinstance(item.get(key),list) and all(isinstance(v,str) for v in item[key]), 'bridge needs string lists')
            bridges.append({'product_or_offer':scopes[series[sid]['scope_id']].get('product_or_offer', data['product_or_offer']),'target_market':market,'customer_type':item['customer_type'],'industry_lens':data['industry_lens'],'seller_context':data['seller_context'],'search_keywords':item['search_keywords'],'exclude_terms':item['exclude_terms'],'market_evidence_ids':row['evidence_ids'],'market_tier':tier,'market_research_seller_role':data['seller_role'],'synthetic':data.get('synthetic',False),'research_reference':'rankings.json','research_series_id':sid,'research_scope_id':series[sid]['scope_id'],'approval_status':'draft','requires_user_market_selection':True})
    claims=data.get('claims',[])
    require(isinstance(claims,list), 'claims must be list')
    for claim in claims:
        require(isinstance(claim,dict) and claim.get('type') in ('observation','inference','missing') and isinstance(claim.get('text'),str), 'invalid claim')
        refs=claim.get('evidence_ids',[])
        require(isinstance(refs,list) and all(ref in sources for ref in refs), 'unknown claim evidence')
        require(claim['type']=='missing' or bool(refs), 'material claim needs evidence')
    errors=data.get('collection_errors',[])
    require(isinstance(errors,list), 'collection_errors must be list')
    return {'status':'draft_for_review','seller_role':data['seller_role'],'product_or_offer':data['product_or_offer'],'sources':sources,'scopes':scopes,'rankings':rankings,'decisions':decisions,'claims':claims,'collection_errors':errors,'synthetic':data.get('synthetic',False)},raw,bridges

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-json',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args()
    original=args.input_json.read_bytes()
    report,rows,bridge=build(json.loads(original))
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    for name,value in [('rankings.json',report),('discovery-bridge.json',bridge),('input-snapshot.json',json.loads(original))]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    fields=sorted({key for row in rows for key in row})
    with (out/'records.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    text=['# 市场调研计算底稿 / Market research worksheet', 'SYNTHETIC DEMO — 非真实市场数据' if report['synthetic'] else 'draft_for_review：需补充业务解读及审核。', '金额单位 USD；下游brief为draft，不自动搜客。']
    for sid,ranking in report['rankings'].items():
        text += ['## '+sid, f"{ranking['base_year']}→{ranking['year']} | {ranking['flow']} | {ranking['coverage']}",ranking['coverage_note']]
        for field in ('size','positive_delta','positive_growth'):
            text += ['### '+field, f"可用{ranking['eligible_counts'][field]}条，显示{len(ranking[field])}条；增速基数门槛USD {ranking['growth_base_min_usd']}。",'|市场|基期|本期|增量|增速%|异常|','|---|---:|---:|---:|---:|---|']
            for r in ranking[field]:text += ['|'+'|'.join(str(r[k]) for k in ('market','base_usd','current_usd','delta_usd','growth_pct','anomaly'))+'|']
    text += ['## Sources']+[f"- {s['id']}: {s['url']} (retrieved {s['retrieved_at']}; {s['quality']})" for s in report['sources'].values()]
    text += ['## Decisions (inference / draft)']+[f"- {d['market']} / {d['seller_role']}: {d['tier']}" for d in report['decisions']]
    text += ['## Collection errors',json.dumps(report['collection_errors'],ensure_ascii=False)]
    (out/'report.md').write_text('\n\n'.join(text)+'\n')
    manifest={'status':'draft_for_review','input_sha256':hashlib.sha256(original).hexdigest(),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name in ('rankings.json','records.csv','discovery-bridge.json','report.md','input-snapshot.json')}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Wrote offline research worksheet and draft bridge to',out)

if __name__=='__main__':
    main()
