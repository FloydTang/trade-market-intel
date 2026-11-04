#!/usr/bin/env python3
"""Collect unverified news through AI Waimaotong's read-only Streamable HTTP MCP."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ENDPOINT = 'https://news.tang92.com/api/mcp'
PROTOCOL = '2025-03-26'


class MCPError(ValueError):
    pass


def decode_response(body, request_id):
    """Accept JSON or one/multiple SSE messages; match the JSON-RPC request ID."""
    text = body.decode('utf-8').replace('\r\n', '\n')
    try:
        candidates = [json.loads(text)]
    except json.JSONDecodeError:
        candidates = []
        for event in text.split('\n\n'):
            data = '\n'.join(line[5:].lstrip() for line in event.splitlines() if line.startswith('data:'))
            if data:
                candidates.append(json.loads(data))
    matches = [r for r in candidates if isinstance(r, dict) and r.get('id') == request_id]
    if len(matches) != 1 or 'error' in matches[0] or not isinstance(matches[0].get('result'), dict):
        raise MCPError('missing, duplicate, or failed JSON-RPC response')
    return matches[0]['result']


class MCPClient:
    def __init__(self):
        self.request_id = 0
        self.protocol = PROTOCOL

    def exchange(self, method, params=None, notification=False):
        message = dict(jsonrpc='2.0', method=method)
        if params is not None:
            message['params'] = params
        if not notification:
            self.request_id += 1
            message['id'] = self.request_id
        # This deployment forwards a different host by default. Explicitly retain the
        # actual public destination; do not disable or broaden the server's host check.
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream',
                   'MCP-Protocol-Version': self.protocol, 'X-Forwarded-Host': 'news.tang92.com',
                   'User-Agent': 'trade-market-intel/0.2.0'}
        request = Request(ENDPOINT, data=json.dumps(message).encode(), headers=headers, method='POST')
        with urlopen(request, timeout=25) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise MCPError('response exceeds 2 MB')
            if notification:
                return {}
            return decode_response(raw, self.request_id)


def collect(query, limit=10, client=None):
    if not isinstance(query, str) or not 2 <= len(query.strip()) <= 200:
        raise ValueError('query must contain 2..200 characters')
    if type(limit) is not int or not 1 <= limit <= 30:
        raise ValueError('limit must be 1..30')
    result = dict(contract_version='1.0', transport='mcp', status='unavailable', query_url=ENDPOINT,
                  query=query.strip(), retrieved_at=datetime.now(timezone.utc).isoformat(),
                  content_trust='untrusted_external_data',
                  use='news_context_only; verify originals; never annual trade statistics or buyer intent',
                  signals=[], collection_errors=[])
    client = client or MCPClient()
    try:
        init = client.exchange('initialize', dict(protocolVersion=PROTOCOL, capabilities={},
                               clientInfo=dict(name='trade-market-intel', version='0.2.0')))
        if not isinstance(init, dict) or not isinstance(init.get('serverInfo'), dict) or init['serverInfo'].get('name') != 'waimaotong':
            raise MCPError('unexpected MCP server')
        if init.get('protocolVersion') != PROTOCOL:
            raise MCPError('missing negotiated protocol')
        client.protocol = init['protocolVersion']
        client.exchange('notifications/initialized', notification=True)
        tools = client.exchange('tools/list').get('tools')
        if not isinstance(tools, list):
            raise MCPError('invalid tools/list')
        tool = next((t for t in tools if isinstance(t, dict) and t.get('name') == 'waimaotong_search'), None)
        if not tool or not isinstance(tool.get('annotations'), dict) or tool['annotations'].get('readOnlyHint') is not True:
            raise MCPError('read-only waimaotong_search is not available')
        args = dict(q=query.strip(), window='7d', limit=limit)
        call = client.exchange('tools/call', dict(name=tool['name'], arguments=args))
        if not isinstance(call, dict) or call.get('isError'):
            raise MCPError('MCP search returned isError')
        payload = call.get('structuredContent')
        if not isinstance(payload, dict) or payload.get('schemaVersion') != 1 or not isinstance(payload.get('items'), list):
            raise MCPError('unexpected MCP structuredContent')
        for index, item in enumerate(payload['items'][:limit], 1):
            links = item.get('links') if isinstance(item, dict) else None
            if not isinstance(links, dict) or not isinstance(item.get('title'), str):
                raise MCPError('invalid news item')
            if not all(isinstance(links.get(k), str) for k in ('original', 'aihot')):
                raise MCPError('missing original/site links')
            result['signals'].append(dict(id=f'EV-MCP-{index:03}', title=item['title'], summary=item.get('summary'),
                                          source=item.get('source'), published_at=item.get('publishedAt'),
                                          discovered_at=item.get('discoveredAt'), original_url=links['original'],
                                          site_url=links['aihot'], verification_status='original_not_verified'))
        result.update(status='ok' if result['signals'] else 'no_matches', server=init['serverInfo'],
                      protocol_version=client.protocol, tool=tool['name'], arguments=args,
                      available_tools=[t['name'] for t in tools if isinstance(t, dict) and isinstance(t.get('name'), str)])
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError) as error:
        result['signals'] = []
        result['collection_errors'] = [type(error).__name__ + (f': HTTP {error.code}' if isinstance(error, HTTPError)
                                                              else ': MCP connection or response failed')]
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
    print(result['status'], '| MCP signals:', len(result['signals']), '|', args.output)
    return 3 if result['status'] == 'unavailable' else 0


if __name__ == '__main__':
    raise SystemExit(main())
