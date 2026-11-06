import json,re,hashlib
from pathlib import Path
from urllib.parse import urljoin,urlparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
from bs4 import BeautifulSoup
norm=lambda v:re.sub('[^a-z0-9]','',v.lower())
missing={norm(r['name']):r['name'] for r in json.load(open('/private/tmp/ava-current-missing-logos.json'))}
out=Path('/private/tmp/ava-broader-brand-logos');out.mkdir(exist_ok=True)
candidates=[]
def extract(source,soup):
 rows=[]
 for img in soup.find_all('img'):
  src=img.get('data-src') or img.get('src') or '';name=img.get('alt','').strip()
  if not src or any(x in src.lower() for x in ['default','placeholder','logo.e12','shopbrand','/icon.']):continue
  key=norm(name)
  if key not in missing:
   a=img.find_parent('a')
   if a and '/brand/' in a.get('href',''):key=norm(a.get_text(' ',strip=True))
  if key not in missing:continue
  if not any(x in src.lower() for x in ['brands/','option_images/','categories/','company_logo']):continue
  rows.append({'brand':missing[key],'source':source,'image_url':urljoin(source,src)})
 return rows
root=Path('/private/tmp/ava-retailer-logo-sources')
for host,url in [('sianwholesale.com','https://sianwholesale.com/brands'),('ahmu.co.uk','https://ahmu.co.uk/category/shop-brands-a-z'),('shop.nilapharm.com','https://shop.nilapharm.com/brands/A/')]:
 soup=BeautifulSoup((root/(host+'.html')).read_text(),'html.parser');candidates.extend(extract(url,soup))
seed=BeautifulSoup((root/'shop.nilapharm.com.html').read_text(),'html.parser')
queue={urljoin('https://shop.nilapharm.com',a['href']) for a in seed.select('a[href]') if re.match(r'^/brands/[A-Z]/$',a['href'])}
visited={'https://shop.nilapharm.com/brands/A/'}
def fetch(url):
 try:
  r=requests.get(url,timeout=15);r.raise_for_status();s=BeautifulSoup(r.content,'html.parser')
  rows=extract(url,s)
  links={urljoin(url,a['href']) for a in s.select('a[href]') if 'page=' in a['href'] and '/brands/' in a['href']}
  print(url,len(rows),flush=True)
  return rows,links
 except Exception:return [],set()
while queue and len(visited)<150:
 batch=list(queue-visited);queue=set();visited.update(batch)
 with ThreadPoolExecutor(max_workers=5) as pool:
  for rows,links in pool.map(fetch,batch):candidates.extend(rows);queue.update(links-visited)
# Observed trade-directory listing has an explicitly labelled H&B logo.
s=BeautifulSoup((root/'www.iabuk.com.html').read_text(),'html.parser')
for img in s.find_all('img'):
 if 'Holland & Barret International logo' in img.get('alt',''):
  candidates.append({'brand':'Holland & Barrett','source':'https://www.iabuk.com/member-directory/holland-barret-international','image_url':urljoin('https://www.iabuk.com',img['src'])})
unique={(r['brand'],r['image_url']):r for r in candidates};candidates=list(unique.values())
def download(row):
 try:
  r=requests.get(row['image_url'],timeout=15);r.raise_for_status()
  if len(r.content)>4*1024*1024:return None
  p=out/(hashlib.sha256((row['brand']+row['image_url']).encode()).hexdigest()[:20]+'.source');p.write_bytes(r.content);return dict(row,path=str(p))
 except Exception:return None
with ThreadPoolExecutor(max_workers=5) as pool:downloaded=[r for r in pool.map(download,candidates) if r]
(out/'manifest.json').write_text(json.dumps(downloaded,indent=2));(out/'pages.json').write_text(json.dumps(sorted(visited),indent=2));print('DONE',len(downloaded),'assets',len(set(r['brand'] for r in downloaded)),'brands',flush=True)
