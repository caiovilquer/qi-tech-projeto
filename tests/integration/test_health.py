import requests
from conftest import API, TOKEN, MONITOR


def test_probes_and_credentials():
    home = requests.get(API+'/', timeout=(3,30))
    assert home.status_code == 200
    assert home.json() == {'service':'banking-api'}
    live = requests.get(API+'/health_check', timeout=(3,30))
    assert live.status_code == 204
    assert live.content == b''
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


# Public error translations are contract expectations from the original ZIP.
# Keep them independent of src so encoding regressions are detected over HTTP.
FORBIDDEN_TRANSLATION = "Requisição precisa ser interna"
NOT_FOUND_TRANSLATION = (
    "O resource solicitado não pode ser encontrado, mas pode estar disponível "
    "no futuro. Requests subsequentes do cliente são permitidos."
)
ERROR_FIELDS = {'title', 'description', 'translation', 'code'}


def test_missing_internal_token_is_refused_before_routing():
    response = requests.put(API+'/sample', timeout=(3,30))
    assert response.status_code == 403
    assert response.json()['code'] == 'QIT000002'
    assert set(response.json()) == ERROR_FIELDS


def test_unknown_route_returns_base_error_envelope():
    response = requests.put(API+'/sample', headers={'INTERNAL-TOKEN': TOKEN}, timeout=(3,30))
    assert response.status_code == 404
    assert response.json()['code'] == 'QIT000404'
    assert set(response.json()) == ERROR_FIELDS


def test_method_not_allowed_returns_base_error_envelope():
    response = requests.put(API+'/health_check', timeout=(3,30))
    assert response.status_code == 405
    assert response.json()['code'] == 'QIT000405'
    assert set(response.json()) == ERROR_FIELDS


def test_error_translation_keeps_original_accents():
    forbidden = requests.put(API+'/sample', timeout=(3,30))
    assert forbidden.status_code == 403
    assert forbidden.json()['code'] == 'QIT000002'
    assert forbidden.json()['translation'] == FORBIDDEN_TRANSLATION

    missing = requests.put(API+'/sample', headers={'INTERNAL-TOKEN': TOKEN}, timeout=(3,30))
    assert missing.status_code == 404
    assert missing.json()['code'] == 'QIT000404'
    assert missing.json()['translation'] == NOT_FOUND_TRANSLATION
