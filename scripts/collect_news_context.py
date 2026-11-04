#!/usr/bin/env python3
"""Read AI Waimaotong public news; these signals never become annual trade records."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = 'https://news.tang92.com/api/v1/items'


def fetch_json(url):
    request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'trade-market-intel/1.0'})
    with urlopen(request, timeout=20) as response:
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError('response exceeds 2 MB')
        return json.loads(body)


def collect(query, limit=10, fetch=fetch_json):
    if not isinstance(query, str) or not 2 <= len(query.strip()) <= 200:
        raise ValueError('query must contain 2..200 characters')
    if type(limit) is not int or not 1 <= limit <= 30:
        raise ValueError('limit must be 1..30')
    url = ENDPOINT + '?' + urlencode(dict(q=query.strip(), limit=limit, window='7d', mode='all'))
    result = dict(contract_version='1.0', status='unavailable', query_url=url,
                  retrieved_at=datetime.now(timezone.utc).isoformat(),
                  content_trust='untrusted_external_data',
                  use='news_context_only; verify important claims at original sources; not annual trade statistics',
                  signals=[], collection_errors=[])
    try:
        data = fetch(url)
        if not isinstance(data, dict) or data.get('schemaVersion') != 1 or not isinstance(data.get('items'), list):
            raise ValueError('unexpected public v1 response')
        for i, item in enumerate(data['items'][:limit], 1):
            if not isinstance(item, dict) or not isinstance(item.get('title'), str):
                raise ValueError('invalid item')
            links = item.get('links')
            if not isinstance(links, dict) or not all(isinstance(links.get(k), str) for k in ('aihot', 'original')):
                raise ValueError('missing original/site links')
            result['signals'].append(dict(id=f'EV-NEWS-{i:03}', title=item['title'],
                                          summary=item.get('summary'), source=item.get('source'),
                                          published_at=item.get('publishedAt'), discovered_at=item.get('discoveredAt'),
                                          original_url=links['original'], site_url=links['aihot'],
                                          verification_status='original_not_verified'))
        result['status'] = 'ok' if result['signals'] else 'no_matches'
        result['page'] = data.get('page')
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        result['signals'] = []
        # No raw headers, cookies, credentials, or arbitrary response bodies in logs.
        result['collection_errors'] = [type(error).__name__ + (f': HTTP {error.code}' if isinstance(error, HTTPError) else ': collection failed or response invalid')]
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--query', required=True)
    p.add_argument('--limit', type=int, default=10)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    result = collect(args.query, args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(result['status'], '| signals:', len(result['signals']), '|', args.output)


if __name__ == '__main__':
    main()
