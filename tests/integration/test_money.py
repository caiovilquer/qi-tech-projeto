import pytest
from helpers import *


@pytest.mark.parametrize('kind,fee',[('PF',200),('PJ',500)])
def test_transfer_fee_replay_and_reconciliation(kind,fee):
    c,_=customer(kind); d,_=customer(); a=account(c); b=account(d)
    assert balance(c,a)==0
    ok(deposit(c,a,10000),201)
    key=uid(); first=ok(transfer(c,a,b,5000,key),201); op=first['operation_key']
    assert balance(c,a)==5000-fee and balance(d,b)==5000
    source=detail(c,a,op); receiver=detail(d,b,op)
    assert [e['role'] for e in source['entries']]==['TRANSFER_DEBIT','FEE_DEBIT']
    assert [e['balance_after_cents'] for e in source['entries']]==[5000,5000-fee]
    assert [e['role'] for e in receiver['entries']]==['TRANSFER_CREDIT']
    assert set(receiver)=={'operation_key','account_key','type','modality','currency','created_at','entries'}
    assert set(receiver['entries'][0])=={'entry_key','role','delta_cents','balance_after_cents'}
    assert sum(e['delta_cents'] for e in reconcile(c,a))+sum(e['delta_cents'] for e in reconcile(d,b))+fee==10000
    assert ok(transfer(c,a,b,5000,key,url=FEE0),201)==first
    assert len(history(c,a))==3
    error(transfer(c,a,b,5001,key),'QIT001012',409)
    error(deposit(c,a,5000,key),'QIT001012',409)
    ok(call('PUT','/accounts/'+a+'/status',c,{'status':'BLOCKED','expected_version':2,'reason':'restriction'}))
    assert ok(transfer(c,a,b,5000,key),201)==first
    error(transfer(c,a,b,1),'QIT001029',409)
    ok(deposit(c,a,1),201)  # blocked can receive own credits


def test_fee_zero_and_atomic_rejection():
    c,_=customer(); d,_=customer(); a=account(c); b=account(d)
    ok(deposit(c,a,10000),201); key=uid()
    before=history(c,a)
    error(transfer(c,a,b,10000,key),'QIT001011',409)
    assert balance(c,a)==10000 and balance(d,b)==0 and history(c,a)==before and history(d,b)==[]
    ok(deposit(c,a,200),201)
    ok(transfer(c,a,b,10000,key),201)  # refused reservation rolled back
    assert balance(c,a)==0
    ok(deposit(c,a,100),201)
    op=ok(transfer(c,a,b,100,url=FEE0),201)['operation_key']
    assert len(detail(c,a,op)['entries'])==1
    reconcile(c,a); reconcile(d,b)


@pytest.mark.parametrize('value',[0,-1,2**53,True,False,1.0,1.5,'100',None])
def test_money_is_strict(value):
    c,_=customer(); a=account(c)
    error(deposit(c,a,value),'QIT000001',400)
    assert balance(c,a)==0 and history(c,a)==[]


def test_ceiling_and_private_errors():
    c,_=customer(); d,_=customer(); a=account(c); b=account(d)
    ok(deposit(d,b,2**53-1),201)
    error(deposit(d,b,1),'QIT001013',409)
    ok(deposit(c,a,1000),201)
    error(transfer(c,a,b,1),'QIT001013',409)
    assert balance(c,a)==1000
    error(transfer(c,a,a,1),'QIT001010',422)
    error(transfer(c,a,uid(),1),'QIT001026',404)
    error(deposit(d,a,1),'QIT001009',404)
    error(call('GET','/accounts/'+a+'/transactions/'+uid(),c),'QIT001028',404)
    reconcile(c,a); reconcile(d,b)


def test_financial_same_key_between_instances():
    c,_=customer(); d,_=customer(); a=account(c); b=account(d)
    ok(deposit(c,a,10000),201); key=uid()
    r=parallel([lambda:transfer(c,a,b,5000,key),lambda:transfer(c,a,b,5000,key,url=FEE0)])
    assert ok(r[0],201)==ok(r[1],201)
    origin=reconcile(c,a); dest=reconcile(d,b)
    assert len(dest)==1 and len(origin) in (2,3)
    fee=-sum(e['delta_cents'] for e in origin if e['role']=='FEE_DEBIT')
    assert balance(c,a)+balance(d,b)+fee==10000


def test_double_spend_first_attempt():
    c,_=customer(); d,_=customer(); a=account(c); b=account(d)
    ok(deposit(c,a,10000),201)
    r=parallel([lambda:transfer(c,a,b,7000),lambda:transfer(c,a,b,7000,url=FEE0)])
    assert sorted(x.status_code for x in r)==[201,409]
    error(next(x for x in r if x.status_code==409),'QIT001011',409)
    assert balance(d,b)==7000
    reconcile(c,a); reconcile(d,b)


def test_opposite_transfers_no_deadlock():
    c,_=customer(); d,_=customer(); a=account(c); b=account(d)
    ok(deposit(c,a,10000),201); ok(deposit(d,b,10000),201)
    r=parallel([lambda:transfer(c,a,b,3000),lambda:transfer(d,b,a,4000,url=FEE0)])
    assert all(x.status_code==201 for x in r),[x.text for x in r]
    assert balance(c,a)==10800 and balance(d,b)==9000
    reconcile(c,a); reconcile(d,b)


def test_credit_to_blocked_and_no_money_to_pending_rejected():
    c,_=customer(); d,p=customer(); a=account(c); b=account(d)
    ok(deposit(c,a,1000),201)
    ok(call('PUT','/accounts/'+b+'/status',d,{'status':'BLOCKED','expected_version':2,'reason':'restriction'}))
    ok(transfer(c,a,b,100),201); assert balance(d,b)==100
    for http in (503,200):
        e,body=customer(); bureau_rule(body['document_number'],status='IRREGULAR',http=http)
        r=call('POST','/accounts',e,{'customer_key':e},uid()); x=r.json()['details']['account_key']
        error(deposit(e,x,1),'QIT001029',409)
        error(transfer(c,a,x,1),'QIT001029',409)
        assert balance(e,x)==0 and history(e,x)==[]
