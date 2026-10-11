import os
from datetime import datetime, timezone

SERVICE_ROOT = os.path.abspath(os.path.dirname(__file__))
SCHEMA_PATH = os.path.join(SERVICE_ROOT, 'schemas')
APP_ENV = os.getenv('APP_ENV', 'sandbox')
SERVICE_NAME = 'banking-api'
DATABASE_URL = os.getenv('DATABASE_URL')
INTERNAL_TOKEN = os.getenv('INTERNAL_TOKEN')
MONITORING_TOKEN = os.getenv('MONITORING_TOKEN')
INTEGRATOR_ID = os.getenv('INTEGRATOR_ID', 'bootcamp-integrator')
BUREAU_URL = os.getenv('BUREAU_URL', 'http://bureau:1080')
MAX_CENTS = 2**53 - 1
BYPASS_ENDPOINTS = ['/', '/health_check']
SANDBOX_DEPOSITS = os.getenv('SANDBOX_DEPOSITS', 'false').lower() == 'true'
TEST_CLOCK_RAW = os.getenv('TEST_CLOCK', '')
TEST_CLOCK = None
FEES = {}
PIX_DAY_LIMIT = None
PIX_NIGHT_LIMIT = None


def config_cents(name, default):
    raw = os.getenv(name, str(default))
    if not raw.isascii() or not raw.isdigit() or not 0 <= int(raw) <= MAX_CENTS:
        raise EnvironmentError(f'Invalid monetary configuration: {name}')
    return int(raw)


def check_variables():
    global TEST_CLOCK, PIX_DAY_LIMIT, PIX_NIGHT_LIMIT
    if not all([DATABASE_URL, INTERNAL_TOKEN, MONITORING_TOKEN, INTEGRATOR_ID]):
        raise EnvironmentError('DATABASE_URL, INTERNAL_TOKEN, MONITORING_TOKEN and INTEGRATOR_ID are required')
    if INTERNAL_TOKEN == MONITORING_TOKEN:
        raise EnvironmentError('Monitoring and integrator credentials must differ')
    if TEST_CLOCK_RAW:
        if APP_ENV != 'test':
            raise EnvironmentError('TEST_CLOCK is only permitted in APP_ENV=test')
        TEST_CLOCK = datetime.fromisoformat(TEST_CLOCK_RAW.replace('Z', '+00:00'))
        if TEST_CLOCK.tzinfo is None:
            raise EnvironmentError('TEST_CLOCK requires timezone')
        TEST_CLOCK = TEST_CLOCK.astimezone(timezone.utc)
    for kind, modality, default in [('PF','INTERNAL',200),('PJ','INTERNAL',500),
                                     ('PF','PIX_SIMULATED',0),('PJ','PIX_SIMULATED',100)]:
        FEES[kind, modality] = config_cents(f'FEE_{kind}_{modality}', default)
    PIX_DAY_LIMIT = config_cents('PIX_DAY_LIMIT', 1000000)
    PIX_NIGHT_LIMIT = config_cents('PIX_NIGHT_LIMIT', 100000)
