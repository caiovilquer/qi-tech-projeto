import os
import random
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import requests
from conftest import API, TOKEN

FEE0 = os.getenv('FEE0_URL', API)
BUREAU = os.getenv('BUREAU_URL', 'http://localhost:1080')


def uid():
    return str(uuid4())


def call(method, path, customer=None, body=None, key=None, url=API, headers=None, params=None):
    h = {'INTERNAL-TOKEN':TOKEN}
    if customer: h['CUSTOMER-KEY'] = customer
    if key: h['Idempotency-Key'] = key
    h.update(headers or {})
    return requests.request(method, url+path, headers=h, json=body, params=params, timeout=(3,30))


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def error(response, code, status):
    assert response.status_code == status, response.text
    assert response.json()['code'] == code, response.text
    assert {'title','description','translation','code'} <= response.json().keys()


def document(kind='PF', alpha=False):
    chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ' if alpha else '0123456789'
    prefix = ''.join(random.choice(chars) for _ in range(9 if kind=='PF' else 12))
    for n in range(2):
        weights = list(range(len(prefix)+1,1,-1)) if kind=='PF' else ([5,4,3,2,9,8,7,6,5,4,3,2] if n==0 else [6,5,4,3,2,9,8,7,6,5,4,3,2])
        r=sum((ord(c)-48)*w for c,w in zip(prefix,weights))%11
        prefix += str(0 if r<2 else 11-r)
    return prefix


def customer(kind='PF', alpha=False):
    payload={'customer_type':kind,'name':'Sandbox Example','document_number':document(kind,alpha)}
    return ok(call('POST','/customers',body=payload,key=uid()),201)['customer_key'], payload


def parallel(actions):
    barrier=Barrier(len(actions))
    def run(f):
        barrier.wait(timeout=10)
        return f()
    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        return list(pool.map(run, actions))


def bureau_rule(doc, status='REGULAR', debt=False, http=200, body=None, delay=None, times=None, priority=100):
    match={'method':'POST','path':'/check','body':{'type':'JSON','json':{'document_number':doc},'matchType':'ONLY_MATCHING_FIELDS'}}
    response={'statusCode':http,'headers':{'Content-Type':['application/json']},
              'body':body if body is not None else {'status':status,'has_debt':debt,'reference':'test-only','checked_at':'2026-10-11T12:00:00Z'}}
    if delay: response['delay']={'timeUnit':'MILLISECONDS','value':delay}
    expectation={'httpRequest':match,'httpResponse':response,'priority':priority}
    if times: expectation['times']={'remainingTimes':times,'unlimited':False}
    r=requests.put(BUREAU+'/mockserver/expectation',json=expectation,timeout=(3,30)); assert r.status_code==201,r.text


def account(c, key=None, url=API):
    return ok(call('POST','/accounts',c,{'customer_key':c},key or uid(),url=url),201)['account_key']


def balance(c,a):
    return ok(call('GET','/accounts/'+a,c))['balance_cents']


def deposit(c,a,amount,key=None,url=API):
    return call('POST','/accounts/'+a+'/deposits',c,{'amount_cents':amount},key or uid(),url=url)


def transfer(c,a,b,amount,key=None,modality='INTERNAL',url=API):
    return call('POST','/accounts/'+a+'/transfers',c,{'destination_account_key':b,'amount_cents':amount,'modality':modality},key or uid(),url=url)


def statement(c,a,**params):
    return ok(call('GET','/accounts/'+a+'/statement',c,params=params))


def detail(c,a,op):
    return ok(call('GET','/accounts/'+a+'/transactions/'+op,c))


def history(c,a):
    entries=[]; cursor=None
    while True:
        page=statement(c,a,**({'cursor':cursor} if cursor else {}),limit=100)
        entries+=page['data']
        if page['is_last_page']: break
        cursor=page['next_cursor']
    assert len({e['entry_key'] for e in entries})==len(entries)
    return entries


def reconcile(c,a):
    entries=list(reversed(history(c,a)))
    running=0
    for e in entries:
        running+=e['delta_cents']
        assert running==e['balance_after_cents']
    assert running==balance(c,a)
    return entries
