import os, sqlite3, datetime, json, base64, secrets, hashlib, hmac
from pathlib import Path
import requests
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv, dotenv_values
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
load_dotenv(Path(__file__).with_name('.env'), override=True)
ROOT=Path(__file__).parent; MEDIA=ROOT/'uploads'; MEDIA.mkdir(exist_ok=True)
DB=ROOT/'greenshield.db'; SECRET=os.getenv('APP_SECRET','dev-only-change-this-secret'); signer=URLSafeTimedSerializer(SECRET)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "https://greenshield-ai-1.onrender.com",
    "https://greenshield-ai-frontend.onrender.com"
],
    allow_methods=["*"],
    allow_headers=["*"],

)
app.mount('/uploads',StaticFiles(directory=MEDIA),name='uploads')
def db():
 c=sqlite3.connect(DB,timeout=15);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def init():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,created_at TEXT);
  CREATE TABLE IF NOT EXISTS plants(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),name TEXT NOT NULL,species TEXT DEFAULT '',location TEXT DEFAULT '',notes TEXT DEFAULT '',photo TEXT DEFAULT '',created_at TEXT);
  CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),plant_id INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,kind TEXT NOT NULL,details TEXT DEFAULT '',photo TEXT DEFAULT '',created_at TEXT);
  CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),plant_id INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,title TEXT NOT NULL,kind TEXT NOT NULL,due_date TEXT NOT NULL,repeat_days INTEGER DEFAULT 0,done INTEGER DEFAULT 0,created_at TEXT);
  CREATE TABLE IF NOT EXISTS recovery(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),plant_id INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,before_photo TEXT NOT NULL,after_photo TEXT NOT NULL,notes TEXT DEFAULT '',created_at TEXT);''')
init()
def hashpw(password):
 salt=secrets.token_bytes(16);dk=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,260000);return salt.hex()+':'+dk.hex()
def verify(password,stored):
 try:
  salt,digest=stored.split(':');return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),260000),bytes.fromhex(digest))
 except Exception:return False
def auth(authorization:str=Header(default='')):
 if not authorization.startswith('Bearer '):raise HTTPException(401,'Login required')
 try:uid=signer.loads(authorization[7:],max_age=60*60*24*14)
 except (BadSignature,SignatureExpired):raise HTTPException(401,'Session expired')
 with db() as c:u=c.execute('SELECT id,email,name FROM users WHERE id=?',(uid,)).fetchone()
 if not u:raise HTTPException(401,'Invalid account')
 return dict(u)
def owned(plant_id,uid):
 with db() as c:p=c.execute('SELECT * FROM plants WHERE id=? AND user_id=?',(plant_id,uid)).fetchone()
 if not p:raise HTTPException(404,'Plant not found')
 return dict(p)
class Credentials(BaseModel):
 email:str;password:str
class Register(Credentials):name:str
class Plant(BaseModel):
 name:str=Field(min_length=1,max_length=100);species:str='';location:str='';notes:str='';photo:str=''
class Event(BaseModel):
 plant_id:int;kind:str;details:str='';photo:str=''
class Task(BaseModel):
 plant_id:int;title:str;kind:str='Water';due_date:str;repeat_days:int=Field(default=0,ge=0,le=365)
class Recovery(BaseModel):
 plant_id:int;before_photo:str;after_photo:str;notes:str=''
@app.post('/api/auth/register')
def register(x:Register):
 if '@' not in x.email or len(x.password)<8 or not x.name.strip():raise HTTPException(400,'Valid email, name and 8+ character password required')
 try:
  with db() as c:
   cur=c.execute('INSERT INTO users(email,name,password,created_at) VALUES(?,?,?,?)',(x.email.strip().lower(),x.name.strip(),hashpw(x.password),now()));uid=cur.lastrowid
 except sqlite3.IntegrityError:raise HTTPException(409,'Email already registered')
 return {'token':signer.dumps(uid),'user':{'id':uid,'name':x.name.strip(),'email':x.email.strip().lower()}}
@app.post('/api/auth/login')
def login(x:Credentials):
 with db() as c:u=c.execute('SELECT * FROM users WHERE email=?',(x.email.strip().lower(),)).fetchone()
 if not u or not verify(x.password,u['password']):raise HTTPException(401,'Invalid email or password')
 return {'token':signer.dumps(u['id']),'user':{'id':u['id'],'name':u['name'],'email':u['email']}}
@app.get('/api/me')
def me(u=Depends(auth)):return u
@app.get('/api/plants')
def plants(u=Depends(auth)):
 with db() as c:return [dict(r) for r in c.execute('SELECT * FROM plants WHERE user_id=? ORDER BY id DESC',(u['id'],))]
@app.post('/api/plants')
def add_plant(x:Plant,u=Depends(auth)):
 with db() as c:cur=c.execute('INSERT INTO plants(user_id,name,species,location,notes,photo,created_at) VALUES(?,?,?,?,?,?,?)',(u['id'],x.name,x.species,x.location,x.notes,x.photo,now()));return {'id':cur.lastrowid}
@app.put('/api/plants/{pid}')
def update_plant(pid:int,x:Plant,u=Depends(auth)):
 owned(pid,u['id'])
 with db() as c:c.execute('UPDATE plants SET name=?,species=?,location=?,notes=?,photo=? WHERE id=?',(x.name,x.species,x.location,x.notes,x.photo,pid))
 return {'ok':True}
@app.delete('/api/plants/{pid}')
def delete_plant(pid:int,u=Depends(auth)):
 owned(pid,u['id'])
 with db() as c:c.execute('DELETE FROM plants WHERE id=?',(pid,))
 return {'ok':True}
@app.get('/api/events')
def events(plant_id:int=0,u=Depends(auth)):
 with db() as c:
  q='SELECT * FROM events WHERE user_id=?';params=[u['id']]
  if plant_id:q+=' AND plant_id=?';params.append(plant_id)
  return [dict(r) for r in c.execute(q+' ORDER BY id DESC',params)]
@app.post('/api/events')
def add_event(x:Event,u=Depends(auth)):
 owned(x.plant_id,u['id'])
 with db() as c:cur=c.execute('INSERT INTO events(user_id,plant_id,kind,details,photo,created_at) VALUES(?,?,?,?,?,?)',(u['id'],x.plant_id,x.kind,x.details,x.photo,now()));return {'id':cur.lastrowid}
@app.get('/api/tasks')
def tasks(u=Depends(auth)):
 with db() as c:return [dict(r) for r in c.execute('SELECT * FROM tasks WHERE user_id=? ORDER BY done,due_date,id',(u['id'],))]
@app.post('/api/tasks')
def add_task(x:Task,u=Depends(auth)):
 owned(x.plant_id,u['id'])
 try:datetime.date.fromisoformat(x.due_date)
 except ValueError:raise HTTPException(400,'Use YYYY-MM-DD date')
 with db() as c:cur=c.execute('INSERT INTO tasks(user_id,plant_id,title,kind,due_date,repeat_days,created_at) VALUES(?,?,?,?,?,?,?)',(u['id'],x.plant_id,x.title,x.kind,x.due_date,x.repeat_days,now()));return {'id':cur.lastrowid}
@app.patch('/api/tasks/{tid}/toggle')
def toggle_task(tid:int,u=Depends(auth)):
 with db() as c:
  t=c.execute('SELECT * FROM tasks WHERE id=? AND user_id=?',(tid,u['id'])).fetchone()
  if not t:raise HTTPException(404,'Task not found')
  new=0 if t['done'] else 1;c.execute('UPDATE tasks SET done=? WHERE id=?',(new,tid))
  if new and t['repeat_days']:
   nxt=(datetime.date.fromisoformat(t['due_date'])+datetime.timedelta(days=t['repeat_days'])).isoformat()
   c.execute('INSERT INTO tasks(user_id,plant_id,title,kind,due_date,repeat_days,created_at) VALUES(?,?,?,?,?,?,?)',(u['id'],t['plant_id'],t['title'],t['kind'],nxt,t['repeat_days'],now()))
  if new:c.execute('INSERT INTO events(user_id,plant_id,kind,details,created_at) VALUES(?,?,?,?,?)',(u['id'],t['plant_id'],t['kind'],t['title']+' completed',now()))
 return {'done':bool(new)}
@app.delete('/api/tasks/{tid}')
def delete_task(tid:int,u=Depends(auth)):
 with db() as c:c.execute('DELETE FROM tasks WHERE id=? AND user_id=?',(tid,u['id']))
 return {'ok':True}
@app.get('/api/recovery')
def recovery(u=Depends(auth)):
 with db() as c:return [dict(r) for r in c.execute('SELECT * FROM recovery WHERE user_id=? ORDER BY id DESC',(u['id'],))]
@app.post('/api/recovery')
def add_recovery(x:Recovery,u=Depends(auth)):
 owned(x.plant_id,u['id'])
 if not x.before_photo or not x.after_photo:raise HTTPException(400,'Two photos required')
 with db() as c:cur=c.execute('INSERT INTO recovery(user_id,plant_id,before_photo,after_photo,notes,created_at) VALUES(?,?,?,?,?,?)',(u['id'],x.plant_id,x.before_photo,x.after_photo,x.notes,now()));return {'id':cur.lastrowid}
@app.post('/api/upload')
async def upload(image:UploadFile=File(...),u=Depends(auth)):
 if image.content_type not in ('image/jpeg','image/png','image/webp'):raise HTTPException(400,'JPEG, PNG or WEBP only')
 raw=await image.read(5_000_001)
 if len(raw)>5_000_000:raise HTTPException(413,'Maximum image size 5 MB')
 if not ((image.content_type=='image/jpeg' and raw.startswith(b'\xff\xd8\xff')) or (image.content_type=='image/png' and raw.startswith(b'\x89PNG\r\n\x1a\n')) or (image.content_type=='image/webp' and raw[:4]==b'RIFF' and raw[8:12]==b'WEBP')):raise HTTPException(400,'Image contents do not match file type')
 suffix={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}[image.content_type]
 name=secrets.token_hex(20)+suffix;(MEDIA/name).write_bytes(raw)
 return {'url':'/uploads/'+name}
def get_groq_key():
 return (dotenv_values(ROOT/'.env').get('GROQ_API_KEY') or os.getenv('GROQ_API_KEY') or '').strip()
def get_groq_model():
 return (dotenv_values(ROOT/'.env').get('GROQ_MODEL') or os.getenv('GROQ_MODEL') or 'meta-llama/llama-4-scout-17b-16e-instruct').strip()
def groq_request(parts, instruction):
 key=get_groq_key()
 if not key:raise HTTPException(503,'Groq is not configured. Set GROQ_API_KEY in backend/.env and restart.')
 content=[]
 for part in parts:
  if 'text' in part:content.append({'type':'text','text':part['text']})
  elif 'inline_data' in part:
   pic=part['inline_data'];content.append({'type':'image_url','image_url':{'url':'data:'+pic['mime_type']+';base64,'+pic['data']}})
 try:
  r=requests.post('https://api.groq.com/openai/v1/chat/completions',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},json={'model':get_groq_model(),'messages':[{'role':'system','content':instruction},{'role':'user','content':content}],'temperature':0.25,'max_tokens':1300},timeout=110)
 except requests.RequestException:raise HTTPException(502,'Could not connect to Groq. Check internet connection.')
 errors={400:'Groq rejected image or request.',401:'Groq API key invalid.',403:'Groq access denied.',404:'Groq vision model unavailable. Check GROQ_MODEL.',413:'Image too large for Groq.',429:'Groq free tier rate limit reached.',500:'Groq service error.',503:'Groq temporarily unavailable.'}
 if not r.ok:raise HTTPException(502,errors.get(r.status_code,'Groq request failed (HTTP '+str(r.status_code)+').'))
 try:return (r.json()['choices'][0]['message']['content'] or '').strip()
 except (KeyError,IndexError,TypeError,ValueError):raise HTTPException(502,'Groq returned an unexpected response.')
def validate_image(raw,mime):
 if mime not in ('image/jpeg','image/png','image/webp'):raise HTTPException(400,'JPEG, PNG or WEBP only')
 if not raw or len(raw)>5_000_000:raise HTTPException(413,'Image must be under 5 MB')
 if not ((mime=='image/jpeg' and raw.startswith(b'\xff\xd8\xff')) or (mime=='image/png' and raw.startswith(b'\x89PNG\r\n\x1a\n')) or (mime=='image/webp' and raw[:4]==b'RIFF' and raw[8:12]==b'WEBP')):raise HTTPException(400,'Image content does not match its type')
def image_part(raw,mime):return {'inline_data':{'mime_type':mime,'data':base64.b64encode(raw).decode('ascii')}}
@app.get('/api/ai/status')
def ai_status(u=Depends(auth)):
 key=get_groq_key()
 return {'provider':'Groq','configured':bool(key),'env_file_exists':(ROOT/'.env').is_file(),'model':get_groq_model(),'message':'Groq key configured; run a diagnosis to verify connectivity.' if key else 'Add GROQ_API_KEY to backend/.env.'}
@app.post('/api/diagnose')
async def diagnose(image:UploadFile=File(...),plant_id:int=Form(0),language:str=Form('English'),u=Depends(auth)):
 if plant_id:owned(plant_id,u['id'])
 raw=await image.read(5_000_001);validate_image(raw,image.content_type)
 instruction='You are GreenShield AI, a cautious horticultural assistant. Never claim a definitive disease diagnosis from one photo. Avoid dangerous chemical mixing and give safe practical care guidance.'
 prompt=f'Answer in {language}. Analyze the plant image. Structure the answer as: 1. Visible symptoms 2. Possible causes with uncertainty 3. Immediate safe actions 4. Care plan for the next 7 days 5. When to consult a local expert. If the photo is not a plant, say so.'
 answer=groq_request([{'text':prompt},image_part(raw,image.content_type)],instruction)
 if not answer:raise HTTPException(502,'Groq returned no analysis. Please retry.')
 if plant_id:
  with db() as c:c.execute('INSERT INTO events(user_id,plant_id,kind,details,created_at) VALUES(?,?,?,?,?)',(u['id'],plant_id,'AI diagnosis',answer,now()))
 return {'analysis':answer,'model':get_groq_model()}
@app.post('/api/ai/compare')
async def compare_images(before:UploadFile=File(...),after:UploadFile=File(...),language:str=Form('English'),plant_id:int=Form(0),u=Depends(auth)):
 if plant_id:owned(plant_id,u['id'])
 old=await before.read(5_000_001);new=await after.read(5_000_001)
 validate_image(old,before.content_type);validate_image(new,after.content_type)
 instruction='You compare plant photos cautiously. Different lighting, framing and angles can make changes unreliable. Never invent a numeric recovery percentage.'
 answer=groq_request([{'text':f'Answer in {language}. Image 1 is BEFORE and image 2 is AFTER. Compare visible leaf color, damage, wilting and new growth. Explain evidence of improvement or worsening, uncertainty due to photo conditions, and recommended next steps.'},{'text':'BEFORE'},image_part(old,before.content_type),{'text':'AFTER'},image_part(new,after.content_type)],instruction)
 if not answer:raise HTTPException(502,'Groq returned no comparison.')
 if plant_id:
  with db() as c:c.execute('INSERT INTO events(user_id,plant_id,kind,details,created_at) VALUES(?,?,?,?,?)',(u['id'],plant_id,'AI recovery comparison',answer,now()))
 return {'analysis':answer,'model':get_groq_model()}
@app.get('/api/recommendations')
def recommendations(u=Depends(auth)):
 with db() as c:
  ps=[dict(r) for r in c.execute('SELECT * FROM plants WHERE user_id=?',(u['id'],))]
  ts=[dict(r) for r in c.execute('SELECT * FROM tasks WHERE user_id=? AND done=0',(u['id'],))]
 today=datetime.date.today().isoformat();out=[]
 for t in ts:
  if t['due_date']<=today:out.append({'plant_id':t['plant_id'],'text':('Overdue: ' if t['due_date']<today else 'Due today: ')+t['title'],'type':'urgent'})
 for p in ps:
  if not any(t['plant_id']==p['id'] for t in ts):out.append({'plant_id':p['id'],'text':'Create a care schedule for '+p['name'],'type':'tip'})
 return out
@app.get('/api/health')
def health():return {'status':'ok'}


# PayPal subscriptions: server-only credentials; never trust client-reported payments.
PAYPAL_ENV=(dotenv_values(ROOT/'.env').get('PAYPAL_ENV') or os.getenv('PAYPAL_ENV','sandbox')).lower()
PAYPAL_BASE='https://api-m.paypal.com' if PAYPAL_ENV=='live' else 'https://api-m.sandbox.paypal.com'
PLAN_KEYS={'Pro':{'monthly':'PAYPAL_PRO_MONTHLY_PLAN_ID','annual':'PAYPAL_PRO_ANNUAL_PLAN_ID'},'Premium':{'monthly':'PAYPAL_PREMIUM_MONTHLY_PLAN_ID','annual':'PAYPAL_PREMIUM_ANNUAL_PLAN_ID'}}
def setting(name,default=''):
 return (dotenv_values(ROOT/'.env').get(name) or os.getenv(name) or default).strip()
def paypal_token():
 cid=setting('PAYPAL_CLIENT_ID');secret=setting('PAYPAL_CLIENT_SECRET')
 if not cid or not secret:raise HTTPException(503,'PayPal is not configured')
 try:
  r=requests.post(PAYPAL_BASE+'/v1/oauth2/token',auth=(cid,secret),data={'grant_type':'client_credentials'},timeout=15);r.raise_for_status();return r.json()['access_token']
 except (requests.RequestException,KeyError):raise HTTPException(502,'PayPal authorization failed')
def paypal_api(method,path,payload=None):
 try:
  r=requests.request(method,PAYPAL_BASE+path,headers={'Authorization':'Bearer '+paypal_token(),'Content-Type':'application/json','Accept':'application/json'},json=payload,timeout=20)
  if not r.ok:raise HTTPException(502,'PayPal request failed: '+str(r.status_code))
  return r.json() if r.content else {}
 except requests.RequestException:raise HTTPException(502,'PayPal unavailable')
def subscription_table():
 with db() as c:c.execute('''CREATE TABLE IF NOT EXISTS subscriptions(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),paypal_id TEXT NOT NULL UNIQUE,plan TEXT NOT NULL,period TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDING',created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
subscription_table()
@app.get('/api/billing/config')
def billing_config(u=Depends(auth)):
 enabled=bool(setting('PAYPAL_CLIENT_ID') and setting('PAYPAL_CLIENT_SECRET'))
 return {'enabled':enabled,'environment':PAYPAL_ENV,'billing_currency':'EUR','plans':{name:{period:bool(setting(key)) for period,key in periods.items()} for name,periods in PLAN_KEYS.items()}}
class SubscriptionChoice(BaseModel):
 plan:str;period:str
@app.post('/api/billing/subscribe')
def create_subscription(x:SubscriptionChoice,u=Depends(auth)):
 key=PLAN_KEYS.get(x.plan,{}).get(x.period)
 if not key:raise HTTPException(400,'Invalid subscription choice')
 plan_id=setting(key)
 if not plan_id:raise HTTPException(503,'This PayPal plan is not configured')
 front=setting('PUBLIC_FRONTEND_URL','http://localhost:5173').rstrip('/')
 data=paypal_api('POST','/v1/billing/subscriptions',{'plan_id':plan_id,'custom_id':str(u['id']),'application_context':{'brand_name':'GreenShield AI','user_action':'SUBSCRIBE_NOW','return_url':front+'/?paypal=return','cancel_url':front+'/?paypal=cancel'}})
 subid=data.get('id');url=next((v.get('href') for v in data.get('links',[]) if v.get('rel')=='approve'),None)
 if not subid or not url:raise HTTPException(502,'PayPal did not return an approval link')
 with db() as c:c.execute('INSERT INTO subscriptions(user_id,paypal_id,plan,period,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(u['id'],subid,x.plan,x.period,'PENDING',now(),now()))
 return {'approval_url':url,'subscription_id':subid}
@app.get('/api/billing/status')
def billing_status(u=Depends(auth)):
 with db() as c:records=[dict(x) for x in c.execute('SELECT paypal_id,plan,period,status,created_at FROM subscriptions WHERE user_id=? ORDER BY id DESC',(u['id'],))]
 return {'subscriptions':records,'active_plan':next((r['plan'] for r in records if r['status']=='ACTIVE'),'Free')}
@app.post('/api/billing/refresh/{subscription_id}')
def refresh_subscription(subscription_id:str,u=Depends(auth)):
 with db() as c:record=c.execute('SELECT * FROM subscriptions WHERE paypal_id=? AND user_id=?',(subscription_id,u['id'])).fetchone()
 if not record:raise HTTPException(404,'Subscription not found')
 data=paypal_api('GET','/v1/billing/subscriptions/'+subscription_id)
 status=data.get('status','UNKNOWN')
 # Verify the returned plan ID, not just the subscription ID or redirect URL.
 expected=setting(PLAN_KEYS[record['plan']][record['period']])
 if not expected or data.get('plan_id')!=expected or str(data.get('custom_id'))!=str(u['id']):raise HTTPException(409,'PayPal subscription ownership or plan mismatch')
 with db() as c:c.execute('UPDATE subscriptions SET status=?,updated_at=? WHERE paypal_id=?',(status,now(),subscription_id))
 return {'status':status}
@app.post('/api/billing/webhook')
async def paypal_webhook(request:Request):
 body=await request.json()
 webhook_id=setting('PAYPAL_WEBHOOK_ID')
 if not webhook_id:raise HTTPException(503,'PayPal webhook is not configured')
 headers=request.headers
 verification=paypal_api('POST','/v1/notifications/verify-webhook-signature',{'auth_algo':headers.get('paypal-auth-algo',''),'cert_url':headers.get('paypal-cert-url',''),'transmission_id':headers.get('paypal-transmission-id',''),'transmission_sig':headers.get('paypal-transmission-sig',''),'transmission_time':headers.get('paypal-transmission-time',''),'webhook_id':webhook_id,'webhook_event':body})
 if verification.get('verification_status')!='SUCCESS':raise HTTPException(400,'Invalid PayPal webhook signature')
 resource=body.get('resource') or {};subid=resource.get('id');event=body.get('event_type','')
 statuses={'BILLING.SUBSCRIPTION.ACTIVATED':'ACTIVE','BILLING.SUBSCRIPTION.CANCELLED':'CANCELLED','BILLING.SUBSCRIPTION.SUSPENDED':'SUSPENDED','BILLING.SUBSCRIPTION.EXPIRED':'EXPIRED','BILLING.SUBSCRIPTION.PAYMENT.FAILED':'SUSPENDED'}
 if subid and event in statuses:
  with db() as c:c.execute('UPDATE subscriptions SET status=?,updated_at=? WHERE paypal_id=?',(statuses[event],now(),subid))
 return {'received':True}

@app.post('/api/billing/cancel/{subscription_id}')
def cancel_subscription(subscription_id:str,u=Depends(auth)):
 with db() as c:record=c.execute('SELECT * FROM subscriptions WHERE paypal_id=? AND user_id=?',(subscription_id,u['id'])).fetchone()
 if not record:raise HTTPException(404,'Subscription not found')
 if record['status'] in ('CANCELLED','EXPIRED'):return {'status':record['status']}
 paypal_api('POST','/v1/billing/subscriptions/'+subscription_id+'/cancel',{'reason':'Cancelled by subscriber'})
 with db() as c:c.execute('UPDATE subscriptions SET status=?,updated_at=? WHERE paypal_id=?',('CANCELLED',now(),subscription_id))
 return {'status':'CANCELLED'}
@app.get('/api/ai/provider-check')
def provider_check(u=Depends(auth)):
 return {'provider':'Groq','configured':bool(get_groq_key()),'model':get_groq_model(),'message':'Configuration only; use Plant Doctor to verify a real API request.'}
@app.get("/")
def home():
    return {"message": "GreenShield AI API is running"}
