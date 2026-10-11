import os
import time
import pytest
import requests

API = os.getenv('API_URL', 'http://localhost:3000')
TOKEN = os.getenv('INTERNAL_TOKEN', 'sandbox-integrator-only')
MONITOR = os.getenv('MONITORING_TOKEN', 'sandbox-monitoring-only')


@pytest.fixture(scope='session', autouse=True)
def ready():
    urls = {API, os.getenv('FEE0_URL', API)}
    deadline = time.monotonic() + 90
    for url in urls:
        while time.monotonic() < deadline:
            try:
                if requests.get(url+'/readiness', headers={'MONITORING-TOKEN': MONITOR}, timeout=(3, 30)).status_code == 204:
                    break
            except requests.RequestException:
                pass
            time.sleep(.5)
        else:
            pytest.fail('Authenticated readiness did not succeed in 90s')
