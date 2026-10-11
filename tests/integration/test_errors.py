"""Input-error regressions: prove refusals and preserved resources over HTTP."""
import pytest
import requests

from conftest import API, TOKEN
from helpers import account, call, customer, error, ok, uid


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
