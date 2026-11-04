#!/usr/bin/env python3
"""Offline check against a real trade-lead-discovery checkout; no search executed."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path
from export_handoff import export
from build_market_report import require


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--discovery-root', required=True, type=Path)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / 'examples/silk-synthetic-input.json').read_text())
    payload, _ = export(data, 'fabric-import', 'Market Alpha', 'offline compatibility check')
    script = args.discovery_root / 'scripts/build_lead_discovery_report.py'
    spec = importlib.util.spec_from_file_location('market_discovery_compat', script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    actual = module.normalize_input(payload)
    for key in ('product_or_offer', 'target_market', 'customer_type', 'industry_lens',
                'search_keywords', 'exclude_terms', 'notes'):
        require(actual[key] == payload[key], 'downstream dropped or changed ' + key)
    for key, value in payload['seller_context'].items():
        require(actual['seller_context'][key] == value, 'downstream changed seller context ' + key)
    screening = module.build_lead_screening_input([], actual)
    require(screening['operator_notes'] == payload['notes'], 'screening bridge dropped market reference')
    print('PASS: actual discovery normalizer and screening bridge preserve the selected route and notes; no network calls.')


if __name__ == '__main__':
    main()
