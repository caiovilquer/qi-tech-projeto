import json
import pytest
from concurrent.futures import ThreadPoolExecutor
from helpers import *


@pytest.mark.parametrize('status,debt,success',[('REGULAR',False,True),('REGULAR',True,True),('IRREGULAR',False,False),('NOT_FOUND',False,False)])
def test_opening_decisions(status,debt,success):
    c,p=customer(); bureau_rule(p['document_number'],status,debt)
    key=uid(); r=call('POST','/accounts',c,{'customer_key':c},key)
    if success:
        a=ok(r,201)['account_key']; state='ACTIVE'
    else:
        error(r,'QIT001030',422); a=r.json()['details']['account_key']; state='REJECTED'
    get=ok(call('GET','/accounts/'+a,c)); assert get['status']==state and get['balance_cents']==0 and get['status_version']==2
    assert call('POST','/accounts',c,{'customer_key':c},key,url=FEE0).json()==r.json()
    assert len(ok(call('GET','/accounts',c))['data'])==1


@pytest.mark.parametrize('failure',['http','invalid','timeout'])
def test_pending_and_resume(failure):
    c,p=customer(); doc=p['document_number']
    if failure=='http': bureau_rule(doc,http=503)
    elif failure=='invalid': bureau_rule(doc,body={'status':'REGULAR','has_debt':'false'})
    else: bureau_rule(doc,delay=5500)
    key=uid(); r=call('POST','/accounts',c,{'customer_key':c},key)
    error(r,'QIT001031',503); a=r.json()['details']['account_key']
    assert ok(call('GET','/accounts/'+a,c))['status']=='PENDING'
    error(call('PUT','/accounts/'+a+'/status',c,{'status':'ACTIVE','reason':'cannot force','expected_version':1}),'QIT001029',409)
    bureau_rule(doc,priority=200)
    assert account(c,key)==a
    assert ok(call('GET','/accounts/'+a,c))['status_version']==2


def test_concurrent_open_and_versioned_status():
    c,p=customer(); key=uid()
    r=parallel([lambda:call('POST','/accounts',c,{'customer_key':c},key),lambda:call('POST','/accounts',c,{'customer_key':c},key,url=FEE0)])
    assert ok(r[0],201)==ok(r[1],201); a=r[0].json()['account_key']
    path='/accounts/'+a+'/status'
    blocked={'status':'BLOCKED','reason':'test restriction','expected_version':2}
    first=ok(call('PUT',path,c,blocked)); assert first['status_version']==3
    assert ok(call('PUT',path,c,blocked))==first
    assert ok(call('PUT',path,c,dict(blocked,expected_version=3)))==first
    error(call('PUT',path,c,dict(blocked,reason='different')),'QIT001034',409)
    assert account(c,key)==a  # immutable approval even while blocked
    assert ok(call('PUT',path,c,{'status':'ACTIVE','reason':'released','expected_version':3}))['status_version']==4
    error(call('PUT',path,c,blocked),'QIT001034',409)
    assert ok(call('GET','/accounts/'+a,c))['status']=='ACTIVE'


@pytest.mark.parametrize("http",[200,503])
def test_late_external_response_cannot_replace_decision(http):
    c,p=customer(); doc=p['document_number']; key=uid()
    with paused_bureau(doc, http) as (arrived, release), ThreadPoolExecutor(max_workers=1) as pool:
        late=pool.submit(call,'POST','/accounts',c,{'customer_key':c},key)
        try:
            assert arrived.wait(timeout=10), 'First request did not reach the bureau'
            winner=call('POST','/accounts',c,{'customer_key':c},key,url=FEE0)
            approved=ok(winner,201)
            assert not late.done(), 'The gated request finished before the bureau was released'
        finally:
            release.set()
        assert ok(late.result(timeout=30),201)==approved
    a=winner.json()['account_key']; assert ok(call('GET','/accounts/'+a,c))['status_version']==2


@pytest.mark.parametrize('invalid', ['\x00', '\ud800', '\udfff'], ids=['nul', 'high-surrogate', 'low-surrogate'])
def test_invalid_bureau_reference_keeps_pending_and_allows_resume(invalid):
    c,p=customer(); key=uid()
    # Raw JSON preserves invalid Unicode escapes across the external mock.
    body=json.dumps({'status':'REGULAR', 'has_debt':False, 'reference':'Test'+invalid,
                     'checked_at':'2026-10-11T12:00:00Z'})
    bureau_rule(p['document_number'],body=body)
    response=call('POST','/accounts',c,{'customer_key':c},key)
    error(response,'QIT001031',503)
    a=response.json()['details']['account_key']
    pending=ok(call('GET','/accounts/'+a,c))
    assert pending['status']=='PENDING' and pending['status_version']==1
    assert pending['balance_cents']==0
    bureau_rule(p['document_number'],priority=200)
    assert account(c,key)==a
    assert ok(call('GET','/accounts/'+a,c))['status_version']==2


def test_account_access_and_listing():
    c,_=customer(); other,_=customer(); a=account(c); b=account(c)
    alien=call('GET','/accounts/'+a,other); missing=call('GET','/accounts/'+uid(),other)
    error(alien,'QIT001009',404); error(missing,'QIT001009',404)
    assert alien.json()==missing.json()  # foreign and missing accounts are indistinguishable
    error(call('POST','/accounts',other,{'customer_key':c},uid()),'QIT001008',404)
    assert ok(call('GET','/accounts',c,params={'limit':1,'page':0}))['data'][0]['account_key']==a
    assert ok(call('GET','/accounts',c,params={'limit':1,'page':1}))['data'][0]['account_key']==b
    assert ok(call('GET','/accounts',c,params={'page':100}))['data']==[]
    for params in [{'page':-1},{'limit':0},{'limit':101},{'unknown':'x'}]:
        error(call('GET','/accounts',c,params=params),'QIT000001',400)
    error(call('PUT','/accounts/'+a+'/status',c,{'status':'BLOCKED','reason':'test','expected_version':2.0}),'QIT000001',400)


def test_creation_key_conflict_across_customers():
    c,_=customer(); d,_=customer(); key=uid(); account(c,key)
    error(call('POST','/accounts',d,{'customer_key':d},key),'QIT001012',409)
