#!/usr/bin/env python3
"""Meaningful invariants on synthetic data; never contacts a live service."""
import copy
import json
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path
from build_market_report import build
from export_handoff import export
from collect_news_context import collect
from urllib.error import URLError

ROOT=Path(__file__).resolve().parents[1]

class MarketChecks(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'examples/synthetic-input.json').read_text())

    def test_rank_units_and_group_exclusion(self):
        report,rows,bridge=build(self.data)
        r=report['rankings']['fabric-import']
        self.assertEqual(r['size'][0]['current_usd'],3000000)
        self.assertEqual(r['positive_delta'][0]['delta_usd'],1000000)
        self.assertAlmostEqual(r['positive_growth'][0]['growth_pct'],50)
        self.assertNotIn('Example Bloc',[x['market'] for x in r['size']])
        self.assertEqual(len(r['positive_growth']),2)
        self.assertTrue(bridge[0]['requires_user_market_selection'])

    def test_missing_zero_and_decline(self):
        report,_,_=build(self.data)
        rows={r['market']:r for r in report['rankings']['fabric-import']['size']}
        self.assertIsNone(rows['Market Missing']['delta_usd'])
        self.assertIsNone(rows['Market Zero']['growth_pct'])
        self.assertEqual(rows['Market Decline']['delta_usd'],-300000)
        self.data['series'][0]['records']=[r for r in self.data['series'][0]['records'] if not (r['market']=='Market Beta' and r['year']==2025)]
        report,_,_=build(self.data)
        self.assertIn('Market Beta',report['rankings']['fabric-import']['base_only_not_assumed_zero'])

    def test_reject_ambiguous_or_invalid_inputs(self):
        for mutation in ['duplicate','unit','negative','bool','unknown_source','overlap','year','unbacked']:
            d=copy.deepcopy(self.data);series=d['series'][0];row=series['records'][0]
            if mutation=='duplicate':series['records'].append(copy.deepcopy(row))
            elif mutation=='unit':row['unit']='EUR'
            elif mutation=='negative':row['value']=-1
            elif mutation=='bool':row['value']=True
            elif mutation=='unknown_source':row['source_id']='missing'
            elif mutation=='overlap':d['scopes'][0]['codes']=['50','500720']
            elif mutation=='year':series['year']=2026
            elif mutation=='unbacked':d['assessments'][0]['role_fit']['evidence_ids']=[]
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):build(d)

    def test_hold_watch_and_no_automatic_bridge(self):
        d=copy.deepcopy(self.data)
        d['assessments'][0]['landed_cost']={'status':'adverse','evidence_ids':['EV-DEMO']}
        report,_,bridge=build(d)
        self.assertEqual(report['decisions'][0]['tier'],'hold');self.assertFalse(bridge)
        d['assessments'][0]['anomaly']=True
        report,_,bridge=build(d)
        self.assertEqual(report['decisions'][0]['tier'],'watch');self.assertFalse(bridge)

    def test_cli_reproducible_and_source_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            args=[sys.executable,str(ROOT/'scripts/build_market_report.py'),'--input-json',str(ROOT/'examples/synthetic-input.json'),'--output-dir',directory]
            subprocess.run(args,check=True,capture_output=True)
            a=(Path(directory)/'manifest.json').read_bytes()
            subprocess.run(args,check=True,capture_output=True)
            self.assertEqual(a,(Path(directory)/'manifest.json').read_bytes())
            self.assertIn('EV-DEMO',(Path(directory)/'records.csv').read_text())

    def test_growth_ranks_full_universe_before_top_n(self):
        records = []
        for i in range(25):
            for year,value in ((2024,100-i),(2025,101-i)):
                records.append(dict(market=f'M{i:02}',market_kind='country',year=year,
                                    value=value,unit='million_usd',source_id='EV-DEMO'))
        self.data['series'][0]['records']=records
        self.data['top_n']=10
        report,_,_=build(self.data)
        r=report['rankings']['fabric-import']
        self.assertEqual(len(r['size']),10)
        self.assertEqual(r['size'][0]['market'],'M00')
        self.assertEqual(r['positive_growth'][0]['market'],'M24')
        self.assertEqual(r['eligible_counts']['size'],25)
        self.data['top_n']=20
        self.assertEqual(len(build(self.data)[0]['rankings']['fabric-import']['size']),20)

    def test_silk_roles_and_flows_are_independent(self):
        data=json.loads((ROOT/'examples/silk-synthetic-input.json').read_text())
        report,_,bridges=build(data)
        self.assertEqual(report['rankings']['fabric-import']['size'][0]['market'],'Market Alpha')
        self.assertEqual(report['rankings']['fabric-china-export']['size'][0]['market'],'Market Beta')
        self.assertEqual({d['seller_role']:d['tier'] for d in report['decisions']},
                         dict(OEM='B',ODM='B',trader='B',brand='hold'))
        self.assertEqual(len(bridges),1)
        data['seller_role']='brand'
        self.assertFalse(build(data)[2])

    def test_selected_handoff_preserves_context_and_stops_hold(self):
        discovery,context=export(self.data,'fabric-import','Market Alpha','demo operator')
        self.assertEqual(discovery['seller_context'],self.data['seller_context'])
        self.assertEqual(context['sources']['EV-DEMO']['id'],'EV-DEMO')
        self.assertFalse(context['outreach_authorized'])
        self.assertEqual(context['status'],'selected_for_discovery_only')
        with self.assertRaises(ValueError):export(self.data,'fabric-import','Market Alpha','')
        self.data['assessments'][0]['role_fit']['status']='unknown'
        with self.assertRaises(ValueError):export(self.data,'fabric-import','Market Alpha','operator')

    def test_source_url_and_boolean_validation(self):
        for mutation in ('bad_url','credentials','synthetic_string','anomaly_string'):
            d=copy.deepcopy(self.data)
            if mutation=='bad_url':d['sources'][0]['url']='https://'
            if mutation=='credentials':d['sources'][0]['url']='https://user:pass@example.com/'
            if mutation=='synthetic_string':d['synthetic']='false'
            if mutation=='anomaly_string':d['series'][0]['records'][0]['anomaly']='false'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):build(d)

    def test_numeric_overflow_and_empty_records(self):
        d=copy.deepcopy(self.data)
        d['series'][0]['records'][0]['value']=float('inf')
        with self.assertRaises(ValueError):build(d)
        d=copy.deepcopy(self.data)
        d['series'][0]['records']=[]
        report,rows,bridges=build(d)
        self.assertFalse(rows)
        self.assertFalse(bridges)
        self.assertEqual(report['rankings']['fabric-import']['size'],[])

    def test_news_adapter_real_contract_empty_failure_and_signals(self):
        def fixture(url):
            self.assertIn('window=7d',url)
            return dict(schemaVersion=1,items=[dict(title='Synthetic signal',summary='Unverified',
                        links=dict(aihot='https://example.com/item',original='https://example.org/source'))])
        result=collect('silk',fetch=fixture)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['signals'][0]['verification_status'],'original_not_verified')
        self.assertEqual(collect('silk',fetch=lambda u: dict(schemaVersion=1,items=[]))['status'],'no_matches')
        def fail(url):raise URLError('offline')
        self.assertEqual(collect('silk',fetch=fail)['status'],'unavailable')
        self.assertEqual(collect('silk',fetch=lambda u: {})['signals'],[])

if __name__=='__main__':unittest.main()
