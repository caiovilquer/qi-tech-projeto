"""Real network fault experiment. All business setup/assertions are HTTP."""
import os
import time
import requests
import pytest
from helpers import *
from conftest import MONITOR

FAULT = os.getenv('FAULT_API', 'http://api-fault:3000')
PROXY = os.getenv('PROXY_URL', 'http://db-proxy:9090')


@pytest.fixture(scope='module', autouse=True)
def ready_fault_api():
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        try:
            r=requests.get(FAULT+'/readiness',headers={'MONITORING-TOKEN':MONITOR},timeout=(3,30))
            if r.status_code==204: break
        except requests.RequestException:
            pass
        time.sleep(.5)
    else: raise AssertionError('Fault API readiness timed out')


def funded_accounts():
    c,_=customer(); d,_=customer(); a=account(c); b=account(d)
    ok(deposit(c,a,10000),201)
    return c,d,a,b


def test_before_commit_failure_rolls_back_and_recovers_once():
    c,d,a,b=funded_accounts()
    before=history(c,a)
    key=uid()
    requests.put(PROXY+'/arm',json={'mode':'before_write'},timeout=(3,30)).raise_for_status()
    error(transfer(c,a,b,1000,key,url=FAULT),'QIT001014',503)
    assert requests.get(PROXY,timeout=(3,30)).json()['event']=='operation_insert_not_forwarded'
    assert balance(c,a)==10000 and balance(d,b)==0 and history(c,a)==before and history(d,b)==[]
    recovered=ok(transfer(c,a,b,1000,key),201)
    assert balance(c,a)==8800 and balance(d,b)==1000
    assert ok(transfer(c,a,b,1000,key,url=FAULT),201)==recovered
    reconcile(c,a); reconcile(d,b)


def test_lost_commit_confirmation_recovers_without_second_debit():
    c,d,a,b=funded_accounts()
    uncertain_key=uid()
    requests.put(PROXY+'/arm',json={'mode':'commit_ack'},timeout=(3,30)).raise_for_status()
    error(transfer(c,a,b,1000,uncertain_key,url=FAULT),'QIT001027',503)
    assert requests.get(PROXY,timeout=(3,30)).json()['event']=='commit_confirmed_by_server_ack_dropped'
    # This attempt COMMITTED although the client received 503.
    assert balance(c,a)==8800 and balance(d,b)==1000
    existing=[e for e in history(d,b) if e['role']=='TRANSFER_CREDIT']
    assert len(existing)==1
    replay=ok(transfer(c,a,b,1000,uncertain_key,url=FEE0),201)
    assert replay['operation_key']==existing[0]['operation_key']
    assert balance(c,a)==8800 and balance(d,b)==1000 and len(history(c,a))==3
    reconcile(c,a); reconcile(d,b)


if __name__=='__main__':
    raise SystemExit(pytest.main(['-q', __file__, '-p', 'no:cacheprovider']))
