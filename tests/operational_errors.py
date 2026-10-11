"""Pytest cases for real faults controlled by the host harness, using only HTTP."""
import json
import os
import time

import pytest
import requests

from conftest import API, MONITOR, TOKEN
from helpers import balance, call, deposit, document, error, history, uid

FAULT = os.getenv('FAULT_API', 'http://api-fault:3000')
ERROR_FIELDS = {'title', 'description', 'translation', 'code'}


@pytest.fixture(scope='session', autouse=True)
def ready():
    # These cases intentionally include failed readiness. Require a live HTTP
    # process rather than a ready database; the tests assert the failure itself.
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            if requests.get(API+'/health_check', timeout=(3,30)).status_code == 204:
                return
        except requests.RequestException:
            pass
        time.sleep(.5)
    pytest.fail('HTTP process did not become live in 90s')


def test_unexpected_failure_returns_safe_500_with_request_id():
    request_id = 'unexpected-failure-'+uid()
    body = {'customer_type':'PF', 'name':'Fictitious failure test', 'document_number':document()}
    response = call('POST', '/customers', body=body, key=uid(), url=FAULT,
                    headers={'X-Request-ID':request_id})
    error(response, 'QIT000500', 500)
    assert set(response.json()) == ERROR_FIELDS
    assert response.headers.get('X-Request-ID') == request_id
    for sensitive in (body['document_number'], TOKEN, '/app/', 'Traceback', 'post_customer.json'):
        assert sensitive not in response.text


def test_database_outage_returns_safe_503():
    state = json.loads(os.environ['SCENARIO_STATE'])
    assert requests.get(API+'/health_check', timeout=(3,30)).status_code == 204
    readiness = requests.get(API+'/readiness', headers={'MONITORING-TOKEN':MONITOR}, timeout=(3,30))
    error(readiness, 'QIT001014', 503)
    assert set(readiness.json()) == ERROR_FIELDS
    rejected = deposit(state['c'], state['a'], 1)
    error(rejected, 'QIT001014', 503)
    assert set(rejected.json()) == ERROR_FIELDS
    for response in (readiness, rejected):
        assert response.headers.get('X-Request-ID')
        assert 'postgresql' not in response.text.lower()
        assert 'Traceback' not in response.text


def test_disabled_sandbox_returns_403_without_financial_effects():
    state = json.loads(os.environ['SCENARIO_STATE'])
    owner, account = state['c'], state['a']
    before, funds = history(owner, account), balance(owner, account)
    rejected = deposit(owner, account, 1)
    error(rejected, 'QIT001035', 403)
    assert set(rejected.json()) == ERROR_FIELDS
    assert balance(owner, account) == funds
    assert history(owner, account) == before
