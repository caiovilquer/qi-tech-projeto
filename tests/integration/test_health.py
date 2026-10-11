import requests
from conftest import API, TOKEN, MONITOR


def test_probes_and_credentials():
    assert requests.get(API+'/', timeout=(3,30)).json() == {'service':'banking-api'}
    assert requests.get(API+'/health_check', timeout=(3,30)).status_code == 204
    for headers in [{}, {'INTERNAL-TOKEN':TOKEN}]:
        r=requests.get(API+'/readiness', headers=headers, timeout=(3,30))
        assert r.status_code==403 and r.json()['code']=='QIT000004'
    assert requests.get(API+'/readiness', headers={'MONITORING-TOKEN':MONITOR}, timeout=(3,30)).status_code==204
    assert requests.get(API+'/customers', headers={'MONITORING-TOKEN':MONITOR}, timeout=(3,30)).status_code==403


def test_non_ascii_credential_is_refused_safely():
    r=requests.get(API+'/readiness',headers={'MONITORING-TOKEN':'é'},timeout=(3,30))
    assert r.status_code==403 and r.json()['code']=='QIT000004'
    r=requests.get(API+'/accounts',headers={'INTERNAL-TOKEN':'é'},timeout=(3,30))
    assert r.status_code==403 and r.json()['code']=='QIT000002'
