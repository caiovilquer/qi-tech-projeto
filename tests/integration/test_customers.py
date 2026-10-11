import pytest
from helpers import *


@pytest.mark.parametrize('kind,alpha',[('PF',False),('PJ',False),('PJ',True)])
def test_registration_and_normalized_replay(kind,alpha):
    doc=document(kind,alpha)
    formatted = f'{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}' if kind=='PF' else f'{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}'
    body={'customer_type':kind,'name':'  Sandbox Example  ','document_number':formatted.lower()}
    key=uid(); first=ok(call('POST','/customers',body=body,key=key),201)
    replay=ok(call('POST','/customers',body=dict(body,name='Sandbox Example',document_number=doc,email=None),key=key,url=FEE0),201)
    assert first==replay
    c=first['customer_key']; read=ok(call('GET','/customers/'+c,c))
    assert read['document_number']==doc and read['email'] is None
    assert set(read)=={'customer_key','customer_type','name','document_number','email','created_at'}
    error(call('POST','/customers',body=body,key=uid()),'QIT001004',409)
    error(call('POST','/customers',body=dict(body,name='Other'),key=key),'QIT001012',409)
    error(call('GET','/customers/'+c,uid()),'QIT001008',404)


def test_concurrent_creation():
    key=uid(); body={'customer_type':'PF','name':'Concurrent','document_number':document()}
    responses=parallel([lambda:call('POST','/customers',body=body,key=key),lambda:call('POST','/customers',body=body,key=key,url=FEE0)])
    assert ok(responses[0],201)==ok(responses[1],201)
    body2=dict(body,document_number=document())
    error(call('POST','/customers',body=body2,key=key),'QIT001012',409)


@pytest.mark.parametrize('doc,code,status',[('11111111111','QIT001003',422),('123.abc.111-11','QIT000001',400),('１２３４５６７８９００','QIT000001',400)])
def test_invalid_documents(doc,code,status):
    error(call('POST','/customers',body={'customer_type':'PF','name':'Example','document_number':doc},key=uid()),code,status)


def test_authorization_and_schema():
    c,body=customer()
    error(call('GET','/customers/'+c),'QIT000005',403)
    error(call('GET','/customers/'+c,headers={'CUSTOMER-KEY':'garbage'}),'QIT000001',400)
    error(call('POST','/customers',body=body),'QIT000001',400)
    error(call('POST','/customers',body=dict(body,unknown=1),key=uid()),'QIT000001',400)
    error(call('POST','/customers',body=body,key=uid(),headers={'INTERNAL-TOKEN':''}),'QIT000002',403)
    error(call('POST','/customers',body=dict(body,name='  '),key=uid()),'QIT000001',400)


def test_official_alpha_example():
    body={'customer_type':'PJ','name':'Official fictitious vector','document_number':'12.ABC.345/01DE-35'}
    key=uid(); r=call('POST','/customers',body=body,key=key)
    assert r.status_code in (201,409)
    if r.status_code==409: error(r,'QIT001004',409)
    error(call('POST','/customers',body=dict(body,document_number='12ABC34501DE36'),key=uid()),'QIT001003',422)
