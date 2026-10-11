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
