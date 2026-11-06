"""Prepare only dedicated local setup fixtures; never reset existing credentials."""
import json,os,secrets,hashlib
from pathlib import Path
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.db import transaction,connection
from apps.accounts.models import User,Pharmacist,Customer
from apps.consultations.models import ClinicianProfile
from apps.lab.models import LabPartner,LabTechnicianProfile
from apps.orders.models import Coupon,ShippingMethod
from apps.products.models import Variant,VariantInventory,Promotion
from apps.payouts.models import PayoutRule
from apps.support.models import SiteSettings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

assert settings.DEBUG and settings.DATABASES['default']['HOST'] in ('localhost','127.0.0.1','::1')
root=Path('docs/test-runs/2026-10-28/setup');private=Path('/private/tmp/ava-setup-20261028-credentials.json')
creds=json.loads(private.read_text()) if private.exists() else {}
users={};profiles=[]
with transaction.atomic():
 for label,role in [('customer',User.CUSTOMER),('other',User.CUSTOMER),('admin',User.ADMIN),('inventory',User.INVENTORY_STAFF),('pharmacist',User.PHARMACIST),('doctor',User.DOCTOR),('pediatrician',User.PEDIATRICIAN),('lab-partner',User.LAB_PARTNER),('lab-technician',User.LAB_TECHNICIAN),('pending-doctor',User.DOCTOR),('suspended-doctor',User.DOCTOR)]:
  email=f'setup28.{label}@avapharmacy.test'
  u,created=User.objects.get_or_create(email=email,defaults={'first_name':'Synthetic Setup QA','last_name':label,'role':role,'is_active':label!='pending-doctor','status':User.STATUS_SUSPENDED if label=='suspended-doctor' else User.STATUS_ACTIVE,'is_staff':role==User.ADMIN})
  if created:
   password=secrets.token_urlsafe(24);u.set_password(password);u.save(update_fields=['password']);creds[email]=password
  assert u.role==role and email in creds, 'Existing fixture needs its original local credentials.'
  users[label]=u
  if role==User.CUSTOMER:Customer.objects.get_or_create(user=u,defaults={'notes':'Synthetic setup fixture only'})
  if role in [User.DOCTOR,User.PEDIATRICIAN]:
   state='pending' if label=='pending-doctor' else 'suspended' if label=='suspended-doctor' else 'active'
   p,_=ClinicianProfile.objects.get_or_create(user=u,provider_type=role,defaults={'name':f'SYNTHETIC QA {label}','specialty':'Paediatrics' if role==User.PEDIATRICIAN else 'General Medicine','email':email,'phone':'0700001234','license_number':f'SYNTHETIC-SETUP28-{label}','license_expiry':timezone.localdate()+timedelta(days=365),'status':state,'is_verified':state=='active','consult_fee':Decimal('500'),'commission':Decimal('10'),'status_note':'Synthetic local setup fixture only'})
   assert p.status==state
   profiles.append({'id':p.pk,'role':role,'status':p.status,'user_id':u.pk,'consult_fee':str(p.consult_fee),'commission_percent':str(p.commission)})
 pharmacist,_=Pharmacist.objects.get_or_create(user=users['pharmacist'],defaults={'license_number':'SYNTHETIC-SETUP28-PHARM','branch_location':'Synthetic QA only','position':'QA Pharmacist','permissions':[Pharmacist.PERMISSION_PRESCRIPTION_REVIEW,Pharmacist.PERMISSION_DISPENSE_ORDERS]})
 assert pharmacist.has_permission(Pharmacist.PERMISSION_PRESCRIPTION_REVIEW)
 partner,_=LabPartner.objects.get_or_create(user=users['lab-partner'],defaults={'name':'SYNTHETIC QA Setup28 Laboratory','email':users['lab-partner'].email,'phone':'0700001234','status':LabPartner.STATUS_VERIFIED,'notes':'Synthetic local setup only'})
 tech,_=LabTechnicianProfile.objects.get_or_create(user=users['lab-technician'],defaults={'partner':partner,'name':'SYNTHETIC QA Setup28 Technician','email':users['lab-technician'].email,'status':'active'})
 assert tech.partner_id==partner.pk and partner.status=='verified' and tech.status=='active'
 now=timezone.now();coupons=[]
 for code,starts,ends in [('SETUPQA28VALID',now-timedelta(days=1),now+timedelta(days=14)),('SETUPQA28EXPIRED',now-timedelta(days=7),now-timedelta(days=1))]:
  c,_=Coupon.objects.get_or_create(code=code,defaults={'description':'SYNTHETIC QA ONLY - setup fixture','discount_type':'percentage','value':10,'minimum_subtotal':100,'maximum_discount':100,'usage_limit':5,'starts_at':starts,'ends_at':ends,'is_active':True})
  coupons.append({'id':c.pk,'code':c.code,'available':c.is_available(users['customer']),'discount_on_200':str(c.calculate_discount(Decimal('200'))),'starts_at':c.starts_at.isoformat(),'ends_at':c.ends_at.isoformat()})
 assert coupons[0]['available'] and not coupons[1]['available']
 fd=os.open(private,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
 with os.fdopen(fd,'w') as f:json.dump(creds,f)

files=[]
for name,title,lines in [('synthetic-prescription.pdf','SYNTHETIC PRESCRIPTION FIXTURE',['Patient: Synthetic QA Fixture (not a real person)','Medicine reference: E2E-QA-20261026-RX','For file-upload testing only. No dispensing authorization.']),('synthetic-lab-result.pdf','SYNTHETIC LAB RESULT FIXTURE',['Sample reference: SETUP28-QA-ONLY','Result: TEST DATA - no clinical result or diagnostic value.','For upload/download testing only. Not a medical report.'])]:
 path=Path('output/pdf/qa-setup')/name;c=canvas.Canvas(str(path),pagesize=A4)
 c.setFillColorRGB(.7,.12,.12);c.setFont('Helvetica-Bold',22);c.drawString(50,770,'SYNTHETIC QA ONLY')
 c.setFillColorRGB(.1,.2,.17);c.setFont('Helvetica-Bold',15);c.drawString(50,727,title)
 c.setFont('Helvetica',11)
 for n,line in enumerate(lines):c.drawString(50,682-n*24,line)
 c.drawString(50,560,'Prepared 28 October 2026 for local Ava Pharmacy setup checks.')
 c.showPage();c.save();files.append({'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
invalid=Path('output/pdf/qa-setup/invalid-upload.txt');invalid.write_text('SYNTHETIC QA ONLY: plain text, deliberately unsupported as a prescription/result PDF upload.\n')
files.append({'path':str(invalid),'bytes':invalid.stat().st_size,'sha256':hashlib.sha256(invalid.read_bytes()).hexdigest()})
site=SiteSettings.get_solo()
with connection.cursor() as cursor:cursor.execute('SELECT 1');assert cursor.fetchone()[0]==1
snapshot={'users':[{'label':label,'id':u.pk,'email':u.email,'role':u.role,'is_active':u.is_active,'status':u.status} for label,u in users.items()], 'clinicians':profiles,'pharmacist_permission':Pharmacist.PERMISSION_PRESCRIPTION_REVIEW,'lab_partner_id':partner.pk,'lab_technician_profile_id':tech.pk,'coupons':coupons,'upload_files':files,
'prices':list(Variant.objects.filter(sku__startswith='E2E-QA-20261026-').values('id','sku','price','requires_prescription')),
'stock':list(VariantInventory.objects.filter(variant__sku__startswith='E2E-QA-20261026-').values('variant__sku','store_listing__store__code','stock_quantity','low_stock_threshold','allow_backorder','max_backorder_quantity')),
'shipping_methods':list(ShippingMethod.objects.filter(is_active=True).values('id','code','name','fee','free_shipping_threshold','estimated_delivery_window')),
'site_delivery':{'base_fee':str(site.base_delivery_fee),'free_threshold':str(site.free_delivery_threshold),'active_zones':site.active_delivery_zones_list},'fallback_delivery':{'fee':settings.SHIPPING_FEE,'free_threshold':settings.FREE_SHIPPING_THRESHOLD},
'active_promotions':list(Promotion.objects.filter(status='active').values('id','title','code','scope','targets','type','value','start_date','end_date','minimum_order_amount','is_stackable','priority')),
'payout_rules':list(PayoutRule.objects.values('role','amount','currency','is_active')),
'background':{'broker':settings.CELERY_BROKER_URL.split('://')[0],'schedule':settings.CELERY_BEAT_SCHEDULE},'credentials_file':str(private)}
assert len(snapshot['prices'])>=6 and len(snapshot['stock'])>=12 and snapshot['shipping_methods']
root.joinpath('fixtures-and-rules.json').write_text(json.dumps(snapshot,indent=2,default=str))
print(json.dumps({'users':len(users),'clinicians':len(profiles),'coupons':coupons,'files':files,'shipping_method_count':len(snapshot['shipping_methods']),'payout_rule_count':len(snapshot['payout_rules'])},default=str))
