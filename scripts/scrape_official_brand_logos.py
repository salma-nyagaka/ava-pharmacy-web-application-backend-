import json,re,hashlib
from pathlib import Path
from urllib.parse import urlparse,urljoin,unquote
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
from bs4 import BeautifulSoup

def norm(v):return re.sub('[^a-z0-9]','',v.lower())
SITES={
'ACM':'https://labo-acm.com/','Eucerin':'https://www.eucerin.co.uk/','Holland & Barrett':'https://www.hollandandbarrett.com/','Dr Teal\'s':'https://www.drteals.com/','BU.KE’':'https://bu-ke.co.ke/','Lulu Life':'https://lulu-life.ch/','Clean & Clear':'https://www.cleanandclear.com/','Uncover':'https://uncoverskincare.com/ke/','OPI':'https://www.opi.com/','Saraya':'https://saraya.world/','Rhino Rescue':'https://rhinorescuestore.com/','Jungle Formula':'https://www.jungleformula.co.uk/','Suresign':'https://www.suresign.com/','Anusol':'https://www.anusol.co.uk/','Leukomed':'https://www.leukoplast.co.uk/','Rennie':'https://www.rennie.co.uk/','Advancis':'https://www.advancispharma.com/','Deep Heat':'https://www.deepheat.com/','Eco Style':'https://ecostyle.com/','Cottons':'https://www.cottons.com.au/','Savlon':'https://www.savlon.co.uk/','Oilatum':'https://www.oilatum.co.uk/','Biofreeze':'https://biofreeze.com/','Sudocrem':'https://www.sudocrem.co.uk/','Neubria':'https://neubria.com/','Fybogel':'https://www.fybogel.co.uk/','Corsodyl':'https://www.corsodyl.co.uk/','Voltaren':'https://www.voltarengel.com/','Mizani':'https://www.mizani.com/','BetterYou':'https://betteryou.com/','Imodium':'https://www.imodium.com/','Geratherm':'https://www.geratherm.com/','Bach Rescue':'https://www.rescueremedy.com/en-gb/','Power Health':'https://www.powerhealth.co.uk/','Alka-Seltzer':'https://www.alkaseltzer.com/','Doppelherz':'https://www.doppelherz.com/','Compeed':'https://www.compeed.co.uk/','Beechams':'https://www.beechams.co.uk/','Similac':'https://www.similac.com/','Chapstick':'https://www.chapstick.com/','Olbas':'https://www.olbas.co.uk/','Nyquil':'https://vicks.com/en-us/shop-products/nyquil','Applied Nutrition':'https://appliednutrition.uk/','Betadine':'https://www.betadine.com/','MuscleTech':'https://www.muscletech.com/','Dark & Lovely':'https://www.darkandlovely.africa/','Daktarin':'https://www.daktarin.co.uk/','Trace Minerals':'https://www.traceminerals.com/','Skyn':'https://skyn.com/','Aquafresh':'https://www.aquafresh.com/','Jergens':'https://www.jergens.com/en-us/','Deep Freeze':'https://www.deepfreeze.co.uk/','Femfresh':'https://www.femfresh.co.uk/','Clear Essence':'https://www.clearessence.com/','Steroplast':'https://www.steroplast.co.uk/','Canderel':'https://www.canderel.co.uk/','Jakemans':'https://jakemans.com/','Starbalm':'https://starbalm.com/','Pantene':'https://pantene.com/en-us/','Nytol':'https://www.nytol.co.uk/','Native':'https://www.nativecos.com/','Buscopan':'https://www.buscopan.com/','Band-Aid':'https://www.band-aid.com/','Dramamine':'https://www.dramamine.com/','Lakanto':'https://www.lakanto.com/','Actikid':'https://actikid.com/','Hedrin':'https://www.hedrin.co.uk/','Sensodyne':'https://www.sensodyne.com/en-us/','Neutrogena':'https://www.neutrogena.com/','Always':'https://www.always.com/en-us','Nivea':'https://www.nivea.co.uk/','CeraVe':'https://www.cerave.com/','La Roche-Posay':'https://www.laroche-posay.us/','Colgate':'https://www.colgate.com/en-us','Sebamed':'https://www.sebamed.com/','Bepanthen':'https://www.bepanthen.co.uk/','Canesten':'https://www.canesten.co.uk/','Panadol':'https://www.panadol.com/','Aleve':'https://www.aleve.com/'}
missing={norm(r['name']) for r in json.load(open('/private/tmp/ava-missing-logo-brands.json'))}
SITES={k:v for k,v in SITES.items() if norm(k) in missing}
out=Path('/private/tmp/ava-official-logos-pass2');out.mkdir(exist_ok=True)
def scrape(pair):
 name,site=pair; key=norm(name);result={'brand':name,'source':site,'candidates':[]}
 try:
  response=requests.get(site,timeout=20,headers={'User-Agent':'Mozilla/5.0'});response.raise_for_status()
  soup=BeautifulSoup(response.content,'html.parser');(out/(key+'.html')).write_text(response.text)
  result['title']=soup.title.get_text(' ',strip=True) if soup.title else ''
  for img in soup.find_all('img'):
   src=img.get('src') or img.get('data-src') or ''; alt=img.get('alt',''); classes=' '.join(img.get('class',[]))+' '+img.get('id','')
   if not src or src.startswith('data:'):continue
   path=norm(unquote(src.split('?')[0])); text=norm(alt+' '+classes)
   if any(x in path for x in ['payment','amazon','visa','klarna','trustpilot','beiersdorf','wholefoods','reckittlogo','alwaysdiscreet']):continue
   parents=' '.join(str(p.get('class',[]))+' '+str(p.get('id','')) for p in list(img.parents)[:3] if getattr(p,'attrs',None))
   labelled='logo' in (text+path+norm(parents))
   branded=key in norm(alt+' '+src) if len(key)>3 else key in norm(alt)
   isheader=img.find_parent('header') is not None or 'header' in parents.lower()
   if not labelled:continue
   if not branded and not isheader and 'logo' not in text:continue
   score=(30 if branded else 0)+(15 if isheader else 0)+(10 if 'logo' in norm(alt) else 0)+(8 if 'logo' in classes.lower() else 0)-(15 if 'white' in path else 0)-(8 if 'footer' in parents.lower() else 0)
   result['candidates'].append({'score':score,'url':urljoin(response.url,src),'alt':alt})
  for svg in soup.select('header svg, .logo svg, .site-logo svg, .header-logo svg, a.logo svg'):
   parent=str(svg.parent.get('class',[]))+' '+str(svg.parent.get('id',''))
   label=svg.get('aria-label','')+' '+parent
   if 'logo' not in label.lower() and key not in norm(label):continue
   markup=str(svg).replace('viewbox=','viewBox=')
   path=out/(key+'-inline-'+str(len(result['candidates']))+'.svg');path.write_text(markup)
   result['candidates'].append({'score':35,'url':response.url+'#inline-logo','local':str(path),'alt':label})
  result['candidates']=sorted(result['candidates'],key=lambda r:-r['score'])[:4]
  seen=set();keep=[]
  for candidate in result['candidates']:
   if candidate['url'] in seen:continue
   seen.add(candidate['url'])
   if candidate.get('local'):data=Path(candidate['local']).read_bytes()
   else:
    try:r=requests.get(candidate['url'],timeout=12);r.raise_for_status();data=r.content
    except Exception:continue
   if len(data)>4*1024*1024:continue
   path=out/(hashlib.sha256((name+candidate['url']).encode()).hexdigest()[:20]+'.source');path.write_bytes(data)
   candidate['path']=str(path);keep.append(candidate)
  result['candidates']=keep
 except Exception as e:result['error']=str(e)[:150]
 return result
rows=[]
with ThreadPoolExecutor(max_workers=6) as pool:
 for future in as_completed([pool.submit(scrape,p) for p in SITES.items()]):
  r=future.result();rows.append(r);print(r['brand'],len(r['candidates']),r.get('title',r.get('error',''))[:80],flush=True)
(out/'candidates.json').write_text(json.dumps(rows,indent=2));print('DONE',len(rows),flush=True)
