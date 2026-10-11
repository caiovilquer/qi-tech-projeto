import pytest
from helpers import *


def test_cursor_pagination_with_new_entries_and_privacy():
    c,_=customer(); d,_=customer(); a=account(c); b=account(d)
    for amount in (1000,2000,3000): ok(deposit(c,a,amount),201)
    first=statement(c,a,limit=2)
    assert [e['delta_cents'] for e in first['data']]==[3000,2000]
    assert first['next_cursor']==first['data'][-1]['entry_key'] and not first['is_last_page']
    ok(deposit(c,a,4000),201)
    last=statement(c,a,limit=2,cursor=first['next_cursor'])
    assert [e['delta_cents'] for e in last['data']]==[1000]
    assert last['next_cursor'] is None and last['is_last_page']
    empty=statement(c,a,cursor=last['data'][0]['entry_key'])
    assert empty['data']==[] and empty['next_cursor'] is None and empty['is_last_page']
    error(call('GET','/accounts/'+b+'/statement',d,params={'cursor':first['next_cursor']}),'QIT001033',400)
    error(call('GET','/accounts/'+a+'/statement',d),'QIT001009',404)
    for marker in ['not-a-uuid',uid(),'']:
        error(call('GET','/accounts/'+a+'/statement',c,params={'cursor':marker}),'QIT001033',400)
    assert set(first)=={'data','limit','next_cursor','is_last_page'}
    assert set(first['data'][0])=={'entry_key','operation_key','role','delta_cents','balance_after_cents','created_at'}
    reconcile(c,a)


def test_time_filters_are_inclusive_exclusive_and_cursor_scoped():
    c,_=customer(); a=account(c)
    ok(deposit(c,a,100),201)
    entry=statement(c,a)['data'][0]; at=entry['created_at']
    assert statement(c,a,created_at_from=at)['data']==[entry]
    assert statement(c,a,created_at_to=at)['data']==[]
    assert statement(c,a,created_at_from='2000-01-01T00:00:00-03:00')['data']==[entry]
    error(call('GET','/accounts/'+a+'/statement',c,params={'cursor':entry['entry_key'],'created_at_to':at}),'QIT001033',400)
    for start,end in [(at,at),('2030-01-01T00:00:00Z','2020-01-01T00:00:00Z')]:
        error(call('GET','/accounts/'+a+'/statement',c,params={'created_at_from':start,'created_at_to':end}),'QIT000010',400)


@pytest.mark.parametrize('params',[{'limit':0},{'limit':101},{'limit':'1.0'}, {'page':0},
    {'created_at_from':'2026-02-30T00:00:00Z'},{'created_at_from':'2026-10-11T12:00:00'},
    {'created_at_to':'invalid'}, {'created_at_to':'2026-10-11T12:00:00+03:60'}, {'unknown':'x'},
    [('limit','1'),('limit','2')]])
def test_bad_query_parameters(params):
    c,_=customer(); a=account(c)
    error(call('GET','/accounts/'+a+'/statement',c,params=params),'QIT000001',400)


def test_detail_recipient_and_other_account_are_isolated():
    c,_=customer(); d,_=customer(); a=account(c); b=account(d); unrelated=account(d)
    ok(deposit(c,a,10000),201); op=ok(transfer(c,a,b,1000),201)['operation_key']
    source=detail(c,a,op); receiver=detail(d,b,op)
    assert [x['delta_cents'] for x in source['entries']]==[-1000,-200]
    assert [x['delta_cents'] for x in receiver['entries']]==[1000]
    assert source['created_at']==receiver['created_at']
    error(call('GET','/accounts/'+unrelated+'/transactions/'+op,d),'QIT001028',404)
    error(call('GET','/accounts/'+a+'/transactions/'+op,d),'QIT001009',404)
    assert [x['role'] for x in statement(c,a)['data'][:2]]==['FEE_DEBIT','TRANSFER_DEBIT']
    times={e['created_at'] for e in history(c,a)+history(d,b) if e['operation_key']==op}
    assert times=={source['created_at']}


def test_concurrent_status_and_debit_observe_serialized_state():
    c,_=customer(); d,_=customer(); a=account(c); b=account(d)
    ok(deposit(c,a,1000),201)
    responses=parallel([lambda:transfer(c,a,b,100),lambda:call('PUT','/accounts/'+a+'/status',c,
                {'status':'BLOCKED','reason':'race','expected_version':2},url=FEE0)])
    money,blocked=responses
    assert blocked.status_code==200,blocked.text
    if money.status_code==201:
        assert balance(c,a)==700 and balance(d,b)==100
        assert len(history(c,a))==3
    else:
        error(money,'QIT001029',409)
        assert balance(c,a)==1000 and balance(d,b)==0 and len(history(c,a))==1
    assert ok(call('GET','/accounts/'+a,c))['status']=='BLOCKED'
    reconcile(c,a); reconcile(d,b)


def test_concurrent_distinct_status_reasons_conflict():
    c,_=customer(); a=account(c)
    r=parallel([lambda:call('PUT','/accounts/'+a+'/status',c,{'status':'BLOCKED','reason':'first','expected_version':2}),
                lambda:call('PUT','/accounts/'+a+'/status',c,{'status':'BLOCKED','reason':'second','expected_version':2},url=FEE0)])
    assert sorted(x.status_code for x in r)==[200,409]
    error(next(x for x in r if x.status_code==409),'QIT001034',409)
    assert ok(call('GET','/accounts/'+a,c))['status_version']==3
