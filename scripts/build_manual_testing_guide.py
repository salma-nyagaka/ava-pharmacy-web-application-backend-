"""Build the self-contained manual checklist; no dependency or server write endpoint."""
from pathlib import Path
import hashlib
import html
import json
import os
import re

SOURCE = Path('docs/manual-end-user-testing-guide.md')
DEST = Path('output/manual-testing/index.html')

def inline(value):
    value=html.escape(value)
    def link(match):
        label,url=match.groups();url=html.unescape(url)
        if not re.match(r'https?://|#',url):url=os.path.relpath((SOURCE.parent/url).resolve(),DEST.parent.resolve())
        return '<a href="'+html.escape(url,quote=True)+'">'+label+'</a>'
    value=re.sub(r'\[([^]]+)\]\(([^)]+)\)',link,value)
    value=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',value)
    value=re.sub(r'`([^`]+)`',r'<code>\1</code>',value)
    return value

def build():
    lines=SOURCE.read_text().splitlines();out=[];toc=[];table=False;listing=False
    for line in lines:
        if not line.startswith('|') and table:out.append('</tbody></table></div>');table=False
        if not re.match(r'^\d+\. ',line) and listing:out.append('</ol>');listing=False
        if line.startswith('#'):
            depth=len(line)-len(line.lstrip('#'));title=line[depth:].strip();anchor=re.sub('[^a-z0-9]+','-',title.lower()).strip('-')
            if depth==2:toc.append((anchor,title))
            out.append(f'<h{depth} id="{anchor}">{inline(title)}</h{depth}>')
            match=re.match(r'(M\d+)\.',title)
            if depth==3 and match:
                case=match[1];out.append(f'<div class="case-result"><label>Case {case} outcome <select aria-label="Case {case} outcome" data-save="result-{case}"><option value="">Not started</option>'+''.join(f'<option>{x}</option>' for x in ['Pass','Fail','Blocked','Partial','N/A'])+f'</select></label><label>References, actual result, evidence and issues<textarea data-save="notes-{case}" rows="3" placeholder="Record order/booking/RX references, screenshots, actual result and N/A reasons here."></textarea><div class="print-value" aria-hidden="true"></div></label></div>')
        elif line.startswith('|'):
            cells=[x.strip() for x in line.strip('|').split('|')]
            if all(re.fullmatch(r':?-+:?',c) for c in cells):continue
            if not table:out.append('<div class="table-wrap"><table><tbody>');table=True
            out.append('<tr>'+''.join('<td>'+inline(c)+'</td>' for c in cells)+'</tr>')
        elif re.match(r'^- \[ \]',line):
            text=line[6:].strip();id=hashlib.sha256(text.encode()).hexdigest()[:14]
            out.append(f'<label class="step"><input type="checkbox" data-save="step-{id}"><span>{inline(text)}</span></label>')
        elif re.match(r'^\d+\. ',line):
            if not listing:out.append('<ol>');listing=True
            out.append('<li>'+inline(re.sub(r'^\d+\. ','',line))+'</li>')
        elif line.startswith('- '):out.append('<p class="bullet">• '+inline(line[2:])+'</p>')
        elif line.strip():out.append('<p>'+inline(line)+'</p>')
    if table:out.append('</tbody></table></div>')
    if listing:out.append('</ol>')
    template='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AvaPharmacy · Manual end-user checklist</title><style>
:root{font:16px/1.65 system-ui,sans-serif;color:#173e34;background:#f3f7f5}*{box-sizing:border-box}body{margin:0}header{background:#fff;padding:30px max(24px,calc((100vw - 1240px)/2));border-bottom:1px solid #d6e4dd}header h1{font-size:30px;line-height:1.2;margin:10px 0}.eyebrow{color:#217757;font-weight:700;font-size:13px}header p{max-width:900px;color:#536b61}.toolbar{position:sticky;top:0;z-index:5;background:#173e34;color:white;padding:12px max(18px,calc((100vw - 1240px)/2));display:flex;gap:10px;align-items:center;flex-wrap:wrap}.toolbar button,.toolbar label{background:white;color:#173e34;border:0;border-radius:6px;padding:7px 12px;cursor:pointer;font:inherit;font-size:13px}#progress{margin-right:auto;font-size:14px}#message{font-size:12px;flex-basis:100%}main{max-width:1290px;margin:25px auto;padding:0 24px;display:grid;grid-template-columns:235px minmax(0,1fr);gap:30px}nav{position:sticky;top:106px;align-self:start;max-height:80vh;overflow:auto;font-size:13px}nav a{display:block;padding:7px 8px;border-bottom:1px solid #dce5df}article{background:#fff;border:1px solid #dce5df;border-radius:12px;padding:30px;min-width:0}h1,h2,h3{line-height:1.3;scroll-margin-top:130px}h1{font-size:29px}h2{font-size:24px;margin-top:46px;border-top:2px solid #dce9e1;padding-top:23px}h3{font-size:20px;margin-top:34px;background:#eaf4ee;padding:15px;border-radius:8px}a{color:#166345;text-decoration:underline;text-underline-offset:2px}p{margin:14px 0}code{background:#f1f5f2;font-size:.88em;overflow-wrap:anywhere;padding:2px 4px;border-radius:4px}.step{display:grid;grid-template-columns:22px minmax(0,1fr);gap:12px;padding:14px 0;border-bottom:1px solid #edf1ee;cursor:pointer}.step input{margin-top:7px;width:18px;height:18px;accent-color:#247d59}.step:has(input:checked){background:#f1f9f4}.case-result{display:grid;gap:10px;border-left:3px solid #7ab899;padding:12px 15px;background:#f8fbf9}.case-result label{font-size:14px;font-weight:650}.case-result textarea{display:block;width:100%;margin-top:6px;font:14px/1.5 system-ui;border:1px solid #cadbd1;border-radius:6px;padding:10px}.case-result select{margin-left:12px;padding:8px;border:1px solid #cadbd1;border-radius:6px;background:#fff}.case-result:has(option[value=""]:checked){border-color:#c5d2cb}input[data-save^="run-"]{padding:9px;width:100%;border:1px solid #cadbd1;border-radius:5px;font:inherit}.run-fields{display:grid;grid-template-columns:1fr 1fr;gap:15px;background:#f3f8f5;padding:20px;border-radius:8px}.run-fields label{font-size:14px}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;margin:20px 0;font-size:14px}td{border:1px solid #dce6e0;padding:10px;vertical-align:top;min-width:80px}tr:first-child{font-weight:700;background:#f2f7f4}.bullet{margin:7px 0}.print-value{display:none}.print-note{font-size:13px;color:#596d63}@media(max-width:850px){main{display:block;padding:0 12px}nav{position:static;max-height:220px;margin-bottom:20px;background:#fff;padding:12px}article{padding:20px}.run-fields{grid-template-columns:1fr}.toolbar{position:static}h1{font-size:25px}h2{font-size:22px}}@media print{body{background:white;color:#000;font-size:10pt}.toolbar,nav,.screen-only{display:none}header{padding:0;border:0}main{display:block;padding:0;margin:0}article{border:0;padding:0}h1{font-size:20pt}h2{font-size:16pt;break-before:auto}h3{font-size:13pt;break-after:avoid}.step{break-inside:avoid;padding:8px 0}.case-result textarea{display:none}.print-value{display:block;white-space:pre-wrap;font-weight:400;overflow-wrap:anywhere;min-height:30px}table{font-size:9pt}.table-wrap{overflow:visible}a{color:#000}code{overflow-wrap:anywhere}.run-fields{display:block}.run-fields label{display:block;margin:8px 0}}
</style></head><body><header><div class="eyebrow">AVA PHARMACY / YOUR MANUAL TEST RUN</div><h1>56 cases · 356 step-by-step actions</h1><p>A fresh browser checklist covering all 110 original acceptance scenarios. Each action includes its expected result. Progress saves in this browser; export a JSON backup before clearing browser data or moving to another device. All fields start blank.</p></header><div class="toolbar"><span id="progress">Loading your checklist…</span><button id="export">Export results</button><label>Import results<input id="import" type="file" accept="application/json,.json" hidden></label><button id="print">Print / Save PDF</button><button id="reset">Reset this run</button><span id="message" role="status"></span></div><main><nav aria-label="Sections">__TOC__</nav><article><section class="run-summary"><h2>Your run details</h2><div class="run-fields">__FIELDS__</div><p class="print-note">Use the outcome selector for each case and the notes box for reference numbers, actual results, screenshot names and N/A reasons. Ticking steps does not automatically mark a case passed.</p></section>__BODY__</article></main><script>
const key='ava-manual-end-user-20261104-v1',fields=[...document.querySelectorAll('[data-save]')],message=document.getElementById('message');
function progress(){const steps=fields.filter(f=>f.type==='checkbox'),results=fields.filter(f=>f.tagName==='SELECT'),counts={};for(const r of results)counts[r.value||'Not started']=(counts[r.value||'Not started']||0)+1;document.getElementById('progress').textContent=`${steps.filter(f=>f.checked).length}/${steps.length} checkboxes · ${results.filter(f=>f.value).length}/${results.length} cases recorded · ${counts.Pass||0} passed · ${counts.Fail||0} failed · ${counts.Blocked||0} blocked`;}
function values(){return Object.fromEntries(fields.map(f=>[f.dataset.save,f.type==='checkbox'?f.checked:f.value]));}
function restore(data){for(const f of fields){const v=data[f.dataset.save];if(f.type==='checkbox')f.checked=v===true;else if(typeof v==='string'){if(f.tagName!=='SELECT'||[...f.options].some(o=>o.value===v))f.value=v;}}progress();}
function save(){try{localStorage.setItem(key,JSON.stringify(values()));message.textContent='Saved in this browser. Export results for a portable backup.';}catch(e){message.textContent='Browser storage unavailable. Export results to retain your progress.';}progress();}
try{restore(JSON.parse(localStorage.getItem(key)||'{}'));}catch(e){message.textContent='Saved data could not be loaded; import a prior export if needed.';progress();}
for(const f of fields)f.addEventListener(f.type==='checkbox'||f.tagName==='SELECT'?'change':'input',save);
document.getElementById('export').onclick=()=>{const data={document:'ava-manual-end-user',version:1,exportedAt:new Date().toISOString(),values:values()};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='ava-manual-test-results-'+new Date().toISOString().slice(0,10)+'.json';a.click();URL.revokeObjectURL(url);message.textContent='Results exported. Keep the file with your evidence.';};
document.getElementById('import').onchange=async event=>{try{const file=event.target.files[0];if(!file)return;if(file.size>2000000)throw Error('File too large');const data=JSON.parse(await file.text());if(data.document!=='ava-manual-end-user'||data.version!==1||!data.values||typeof data.values!=='object')throw Error('This is not a checklist results export');if(!confirm('Replace this browser run with the imported results? Export your current results first if needed.'))return;restore(data.values);save();message.textContent='Results imported.';}catch(e){message.textContent='Import failed: '+e.message;}finally{event.target.value='';}};
window.addEventListener('beforeprint',()=>{for(const f of fields.filter(f=>f.tagName==='TEXTAREA')){if(f.nextElementSibling?.classList.contains('print-value'))f.nextElementSibling.textContent=f.value||'No notes recorded.';}});document.getElementById('print').onclick=()=>window.print();document.getElementById('reset').onclick=()=>{if(!confirm('Clear all checks, outcomes and notes for this browser run? Export results first to keep a copy.'))return;for(const f of fields){if(f.type==='checkbox')f.checked=false;else f.value='';}save();message.textContent='Run reset. All cases are blank.';};
</script></body></html>'''
    labels=['Run ID','Tester / date','Reviewer / date','Website URL / build','Browser / device','Phone browser / device','Customer A / Customer B labels','Staff role partners','Authorized payment amount / phone suffix','Evidence folder / issue references']
    fields=''.join(f'<label>{html.escape(label)}<input data-save="run-{i}" autocomplete="off" placeholder="Fill in for this run"></label>' for i,label in enumerate(labels))
    result=template.replace('__TOC__',''.join(f'<a href="#{a}">{html.escape(t)}</a>' for a,t in toc)).replace('__FIELDS__',fields).replace('__BODY__','\n'.join(out))
    DEST.parent.mkdir(parents=True,exist_ok=True);DEST.write_text(result)
    assert result.count('type="checkbox" data-save=')==364
    assert result.count('<select aria-label="Case M')==56
    print(json.dumps({'output':str(DEST),'cases':56,'action_steps':356,'final_signoff_boxes':8,'external_dependencies':0}))

if __name__=='__main__':build()
