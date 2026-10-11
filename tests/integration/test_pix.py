import pytest
from helpers import *


@pytest.mark.parametrize('kind,fee',[('PF',0),('PJ',100)])
def test_pix_tariff_and_boundary(kind,fee):
    c,_=customer(kind); d,_=customer(); a=account(c); b=account(d)
    ok(deposit(c,a,1000000+fee),201)
    key=uid(); first=ok(transfer(c,a,b,1000000,key,modality='PIX_SIMULATED'),201)
    assert balance(c,a)==0 and balance(d,b)==1000000
    entries=detail(c,a,first['operation_key'])['entries']
    assert [e['role'] for e in entries]==(['TRANSFER_DEBIT'] if fee==0 else ['TRANSFER_DEBIT','FEE_DEBIT'])
    ok(deposit(c,a,1000),201)
    error(transfer(c,a,b,1,modality='PIX_SIMULATED'),'QIT001032',409)
    assert ok(transfer(c,a,b,1000000,key,modality='PIX_SIMULATED',url=FEE0),201)==first
    error(transfer(c,a,b,1000000,key,modality='INTERNAL'),'QIT001012',409)
    reconcile(c,a); reconcile(d,b)


def test_shared_quota_between_accounts_first_attempt():
    c,_=customer(); d,_=customer(); a=account(c); b=account(c); dest=account(d)
    ok(deposit(c,a,700000),201); ok(deposit(c,b,700000),201)
    r=parallel([lambda:transfer(c,a,dest,600000,modality='PIX_SIMULATED'),
                lambda:transfer(c,b,dest,600000,modality='PIX_SIMULATED',url=FEE0)])
    assert sorted(x.status_code for x in r)==[201,409],[x.text for x in r]
    error(next(x for x in r if x.status_code==409),'QIT001032',409)
    assert balance(d,dest)==600000 and balance(c,a)+balance(c,b)==800000
    assert sum(e['role']=='TRANSFER_DEBIT' for e in history(c,a)+history(c,b))==1
    reconcile(c,a); reconcile(c,b); reconcile(d,dest)


def test_self_pix_internal_and_receipts_do_not_restore_quota():
    c,_=customer(); d,_=customer(); a=account(c); b=account(c); dest=account(d)
    ok(deposit(c,a,2000000),201)
    ok(transfer(c,a,b,500000,modality='INTERNAL'),201)
    ok(transfer(c,a,b,1000000,modality='PIX_SIMULATED'),201)
    ok(transfer(c,b,dest,100000,modality='INTERNAL'),201)
    before=[balance(c,a),balance(c,b),balance(d,dest)]
    error(transfer(c,b,a,1,modality='PIX_SIMULATED'),'QIT001032',409)
    assert before==[balance(c,a),balance(c,b),balance(d,dest)]
    reconcile(c,a); reconcile(c,b); reconcile(d,dest)
