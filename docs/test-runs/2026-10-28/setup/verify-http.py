"""Verify prepared QA role logins through the running API; respect throttles."""
import json,time,requests
from pathlib import Path
from django.urls import reverse
from apps.accounts.models import User
from rest_framework_simplejwt.tokens import RefreshToken
creds=json.loads(Path('/private/tmp/ava-setup-20261028-credentials.json').read_text());root=Path('docs/test-runs/2026-10-28/setup');evidence=[]
def save():root.joinpath('http-role-checks.json').write_text(json.dumps(evidence,indent=2))
roles={'customer':'account-profile','other':'account-profile','admin':'admin-dashboard','inventory':'admin-inventory','pharmacist':'pharmacist-prescriptions','doctor':'doctor-dashboard','pediatrician':'pediatrician-dashboard','lab-partner':'lab-partner-dashboard','lab-technician':'lab-dashboard','pending-doctor':None,'suspended-doctor':None}
for label,route in roles.items():
 email=f'setup28.{label}@avapharmacy.test'
 for attempt in range(4):
  response=requests.post('http://localhost:8000'+reverse('login'),json={'email':email,'password':creds[email]},timeout=30)
  if response.status_code!=429:break
  delay=int(response.headers.get('Retry-After','60'))+1
  print('Login throttle respected; continuing after retry window.',flush=True)
  while delay>0:pause=min(delay,30);time.sleep(pause);delay-=pause
 expected=401 if label=='pending-doctor' else 403 if label=='suspended-doctor' else 200
 assert response.status_code==expected,(label,response.status_code,response.text[:300])
 evidence.append({'fixture':label,'check':'login','status':response.status_code,'expected':expected})
 if route:
  payload=response.json();payload=payload.get('data',payload);tokens=payload.get('tokens',payload);access=tokens.get('access') or tokens.get('access_token')
  assert access,(label,'Missing access token')
  session=requests.Session();session.headers['Authorization']='Bearer '+access
  me=session.get('http://localhost:8000'+reverse('me'),timeout=30);assert me.status_code==200,(label,me.text[:200])
  body=me.json();body=body.get('data',body);assert body['id']==User.objects.get(email=email).pk
  result=session.get('http://localhost:8000'+reverse(route),timeout=30)
  assert result.status_code==200,(label,result.status_code,result.text[:300])
  evidence.append({'fixture':label,'check':route,'status':result.status_code,'user_id':body['id'],'role':body['role']})
 else:
  # Even a validly signed token cannot bypass current inactive/suspended state.
  user=User.objects.get(email=email);access=str(RefreshToken.for_user(user).access_token)
  result=requests.get('http://localhost:8000'+reverse('doctor-dashboard'),headers={'Authorization':'Bearer '+access},timeout=30)
  assert result.status_code in (401,403),(label,result.status_code)
  evidence.append({'fixture':label,'check':'restricted doctor dashboard with signed token','status':result.status_code})
 save();print(label+' passed',flush=True)
for name in ['delivery-options','categories','products']:
 result=requests.get('http://localhost:8000'+reverse(name),timeout=30);assert result.status_code==200
 evidence.append({'check':name,'status':result.status_code})
save();print('All setup HTTP checks passed',flush=True)
