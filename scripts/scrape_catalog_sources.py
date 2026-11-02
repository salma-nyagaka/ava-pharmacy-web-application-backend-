"""Read-only catalog source pilot. Outputs factual metadata; never updates catalog rows."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import socket
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests

AGENT = 'AvaPharmacyCatalog/1.0'


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__(); self.meta = {}; self.blocks = []; self.current = None
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            key = attrs.get('property') or attrs.get('name')
            if key: self.meta[key] = attrs.get('content', '')
        if tag == 'script' and attrs.get('type', '').lower() == 'application/ld+json':
            self.current = []
    def handle_data(self, data):
        if self.current is not None: self.current.append(data)
    def handle_endtag(self, tag):
        if tag == 'script' and self.current is not None:
            try: self.blocks.append(json.loads(''.join(self.current)))
            except ValueError: pass
            self.current = None


def product_nodes(value):
    if isinstance(value, list):
        for entry in value: yield from product_nodes(entry)
    elif isinstance(value, dict):
        types = value.get('@type', [])
        if isinstance(types, str): types = [types]
        if 'Product' in types: yield value
        if '@graph' in value: yield from product_nodes(value['@graph'])


def public_https(url):
    u = urlsplit(url)
    if u.scheme != 'https' or not u.hostname or u.username or u.password:
        raise ValueError('Source must be public HTTPS')
    for address in socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(address[4][0]).is_global:
            raise ValueError('Non-public source rejected')


def fetch(session, url):
    for _ in range(5):
        public_https(url)
        with session.get(url, timeout=12, allow_redirects=False, stream=True) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers['Location']); continue
            response.raise_for_status()
            chunks = []; size = 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 2_000_000: raise ValueError('Page exceeds 2 MB pilot limit')
                chunks.append(chunk)
            return b''.join(chunks).decode(response.encoding or 'utf-8', errors='replace'), url
    raise ValueError('Too many redirects')


def inspect(row):
    out = {'variant_id': row['id'], 'sku': row['sku'], 'catalog_name': row['name'],
           'source_page': row['image_source_page_url'], 'status': 'unverified'}
    try:
        session = requests.Session(); session.headers['User-Agent'] = AGENT
        source = urlsplit(out['source_page']); robots_url = source._replace(path='/robots.txt', query='', fragment='').geturl()
        public_https(robots_url)
        response = session.get(robots_url, timeout=8, allow_redirects=False)
        if response.status_code == 200:
            robots = RobotFileParser(); robots.parse(response.text.splitlines())
            if not robots.can_fetch(AGENT, out['source_page']):
                out.update(status='skipped', reason='robots.txt disallows this path'); return out
        elif response.status_code not in (404, 410):
            out.update(status='skipped', reason=f'robots policy unavailable: HTTP {response.status_code}'); return out
        body, final_url = fetch(session, out['source_page'])
        parser = Metadata(); parser.feed(body)
        products = [node for block in parser.blocks for node in product_nodes(block)]
        out.update(status='scraped_candidate', final_source_page=final_url,
                   page_title=parser.meta.get('og:title', ''), image_url=parser.meta.get('og:image', ''),
                   structured_products=[{k: node[k] for k in ['name', 'sku', 'gtin', 'gtin8', 'gtin12', 'gtin13', 'gtin14', 'mpn', 'brand', 'image', 'description', 'size', 'weight', 'color', 'material', 'additionalProperty'] if k in node} for node in products],
                   review_required=True)
        if not out['page_title'] and not products:
            out.update(status='no_product_metadata', reason='No usable structured product metadata; no bypass attempted')
    except Exception as exc:
        out.update(status='failed', reason=str(exc)[:240])
    return out


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--input', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); rows = json.loads(Path(args.input).read_text())
    with ThreadPoolExecutor(max_workers=3) as pool: results = list(pool.map(inspect, rows))
    counts = {status: sum(r['status'] == status for r in results) for status in sorted({r['status'] for r in results})}
    report = {'scraped_at_utc': datetime.now(timezone.utc).isoformat(), 'mode': 'read_only_candidates',
              'catalog_changes': 0, 'description_or_dosage_copied': False, 'summary': counts, 'results': results}
    Path(args.output).write_text(json.dumps(report, indent=2)); print(json.dumps({'processed': len(results), 'summary': counts, 'catalog_changes': 0}))


if __name__ == '__main__': main()
