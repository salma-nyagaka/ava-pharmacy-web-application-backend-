import os, json, re, hashlib, time
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

def norm(s): return re.sub('[^a-z0-9]','',str(s).lower())
rows=json.loads(Path('avapharmacy/apps/products/data/researched_brands.json').read_text())
excluded=['goodlife.co.ke','pharmacyboard','ppb','kipi.go.ke']
sources={}
for row in rows:
 for source in row['sources']:
  if not any(x in source for x in excluded) and not source.endswith('.pdf'):sources.setdefault(source,[]).append(row['brand'])
# Official consumer brand homepages; exact names only, never inferred domains.
extra={'Accu-Chek':'https://www.accu-chek.com/','ACM':'https://labo-acm.com/','Abena':'https://www.abena.com/','CeraVe':'https://www.cerave.com/','Nivea':'https://www.nivea.co.uk/','Eucerin':'https://www.eucerin.co.uk/','Bioderma':'https://www.bioderma.co.uk/','La Roche-Posay':'https://www.laroche-posay.us/','Advil':'https://www.advil.com/','Aleve':'https://www.aleve.com/','Durex':'https://www.durex.co.uk/','Sensodyne':'https://www.sensodyne.com/en-us/','Panadol':'https://www.panadol.com/','Dove':'https://www.dove.com/us/en/home.html','Neutrogena':'https://www.neutrogena.com/','Cetaphil':'https://www.cetaphil.com/us/','Always':'https://www.always.com/en-us','Vaseline':'https://www.vaseline.com/us/en/home.html','Pampers':'https://www.pampers.com/en-us','Garnier':'https://www.garnierusa.com/','Colgate':'https://www.colgate.com/en-us','Listerine':'https://www.listerine.com/','Mucinex':'https://www.mucinex.com/','Dettol':'https://www.dettol.co.uk/','Bepanthen':'https://www.bepanthen.co.uk/','Canesten':'https://www.canesten.co.uk/','Nicorette':'https://www.nicorette.co.uk/','Olay':'https://www.olay.com/','Oral-B':'https://oralb.com/','Sebamed':'https://www.sebamed.com/'}
for name,source in extra.items(): sources.setdefault(source,[]).append(name)
output=Path('/private/tmp/ava-scraped-brand-logos');output.mkdir(exist_ok=True)

def scrape(pair):
 source,names=pair; records=[]
 try:
  response=requests.get(source,timeout=18,headers={'User-Agent':'Mozilla/5.0 (compatible; AvaCatalogLogoReview/1.0)'})
  response.raise_for_status()
  if 'html' not in response.headers.get('Content-Type',''):return []
  soup=BeautifulSoup(response.content,'html.parser')
  for name in set(names):
   key=norm(name); candidates=[]; host=norm(urlparse(response.url).hostname or '')
   for img in soup.find_all('img'):
    src=img.get('src') or img.get('data-src') or ''
    if not src or src.startswith('data:'):continue
    attrs=' '.join([img.get('alt',''),str(img.get('class','')),img.get('id',''),unquote(src.split('?')[0])])
    n=norm(attrs); domainmatch=len(key)>=4 and key in host
    exactbrand=len(key)>=4 and key in n
    if not exactbrand and not (domainmatch and 'logo' in n):continue
    if any(x in n for x in ['payment','facebook','instagram','trustpilot','award']):continue
    score=(10 if exactbrand else 0)+(6 if 'logo' in n else 0)+(4 if key in norm(img.get('alt','')) else 0)
    # Branded product photos are not logos.
    if 'logo' not in n:continue
    candidates.append((score,urljoin(response.url,src)))
   for _,url in sorted(candidates,reverse=True)[:2]:
    try:
     image=requests.get(url,timeout=12);image.raise_for_status()
     if len(image.content)>4*1024*1024:continue
     path=output/(hashlib.sha256((name+url).encode()).hexdigest()[:20]+'.source')
     path.write_bytes(image.content)
     records.append({'brand':name,'source':source,'image_url':url,'path':str(path)});break
    except Exception:pass
 except Exception:pass
 return records
all_rows=[]
with ThreadPoolExecutor(max_workers=6) as pool:
 for future in as_completed([pool.submit(scrape,pair) for pair in sources.items()]):
  rows=future.result();all_rows.extend(rows)
  if rows:print('Found: '+', '.join(r['brand'] for r in rows),flush=True)
(output/'manifest.json').write_text(json.dumps(all_rows,indent=2))
print('TOTAL',len(all_rows),flush=True)
