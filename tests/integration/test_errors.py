"""Input-error regressions: prove refusals and preserved resources over HTTP."""
import pytest
import requests

from conftest import API, TOKEN
from helpers import account, call, customer, document, error, ok, uid


@pytest.mark.parametrize('body', [b'{"name":', b'{"name":"invalid-\xff"}'], ids=['invalid-json', 'invalid-utf8'])
def test_malformed_json_is_a_client_error_without_internal_details(body):
    response = requests.post(API+'/customers', data=body,
                             headers={'INTERNAL-TOKEN':TOKEN, 'Idempotency-Key':uid(),
                                      'Content-Type':'application/json'}, timeout=(3,30))
    error(response, 'QIT000001', 400)
    assert set(response.json()) == {'title', 'description', 'translation', 'code'}
    assert response.headers.get('X-Request-ID')
    assert TOKEN not in response.text
    assert 'Traceback' not in response.text
    assert 'invalid-' not in response.text


def test_unknown_customer_cannot_create_an_account():
    missing = uid()
    response = call('POST', '/accounts', missing, {'customer_key':missing}, uid())
    error(response, 'QIT001008', 404)
    assert 'details' not in response.json()
    error(call('GET', '/customers/'+missing, missing), 'QIT001008', 404)
    error(call('GET', '/accounts', missing), 'QIT001008', 404)


def test_invalid_status_enum_keeps_account_state_and_version():
    owner,_ = customer()
    key = account(owner)
    before = ok(call('GET', '/accounts/'+key, owner))
    response = call('PUT', '/accounts/'+key+'/status', owner,
                    {'status':'CLOSED', 'reason':'Fictitious invalid state',
                     'expected_version':before['status_version']})
    error(response, 'QIT000001', 400)
    assert ok(call('GET', '/accounts/'+key, owner)) == before


@pytest.mark.parametrize('field', ['name', 'email'])
@pytest.mark.parametrize('invalid', ['\x00', '\ud800', '\udfff'], ids=['nul', 'high-surrogate', 'low-surrogate'])
def test_invalid_customer_text_is_refused_without_consuming_key(field, invalid):
    body = {'customer_type':'PF', 'name':'Fictitious text test', 'document_number':document()}
    key = uid()
    response = call('POST', '/customers', body=dict(body, **{field:'Test'+invalid}), key=key)
    error(response, 'QIT000001', 400)
    assert response.headers.get('X-Request-ID')
    created = ok(call('POST', '/customers', body=body, key=key), 201)
    assert ok(call('POST', '/customers', body=body, key=key), 201) == created


@pytest.mark.parametrize('invalid', ['\x00', '\ud800', '\udfff'], ids=['nul', 'high-surrogate', 'low-surrogate'])
def test_invalid_status_reason_preserves_state_and_version(invalid):
    owner,_ = customer()
    key = account(owner)
    before = ok(call('GET', '/accounts/'+key, owner))
    body = {'status':'BLOCKED', 'reason':'Test'+invalid, 'expected_version':before['status_version']}
    error(call('PUT', '/accounts/'+key+'/status', owner, body), 'QIT000001', 400)
    assert ok(call('GET', '/accounts/'+key, owner)) == before
    changed = ok(call('PUT', '/accounts/'+key+'/status', owner, dict(body, reason='Valid reason')))
    assert changed['status'] == 'BLOCKED'
    assert changed['status_version'] == before['status_version']+1


def test_valid_unicode_text_round_trips():
    body = {'customer_type':'PF', 'name':'João fictício 🧪', 'document_number':document()}
    owner = ok(call('POST', '/customers', body=body, key=uid()), 201)['customer_key']
    assert ok(call('GET', '/customers/'+owner, owner))['name'] == body['name']
    key = account(owner)
    body = {'status':'BLOCKED', 'reason':'Restrição de teste 🧪', 'expected_version':2}
    changed = ok(call('PUT', '/accounts/'+key+'/status', owner, body))
    assert changed['status'] == 'BLOCKED'
    assert ok(call('PUT', '/accounts/'+key+'/status', owner, body)) == changed
