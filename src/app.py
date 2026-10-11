from fastapi import FastAPI
from constants import check_variables
from errors import register_error_handlers
from errors.custom_errors import verify_catalog
from middlewares import (register_session_manager_middleware, register_internal_token_middleware,
                         register_request_logger_middleware, register_request_context_middleware)
from resources import HealthCheckResource
from resources.customers import CustomerResource
from resources.accounts import AccountResource
from utils.logger import setup_logging


def create_app():
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    register_session_manager_middleware(application)
    register_internal_token_middleware(application)
    register_request_logger_middleware(application)
    register_request_context_middleware(application)
    health = HealthCheckResource()
    application.add_api_route('/', health.on_get_home, methods=['GET'])
    application.add_api_route('/health_check', health.on_get_health_check, methods=['GET'])
    application.add_api_route('/readiness', health.on_get_readiness, methods=['GET'])
    customers = CustomerResource()
    application.add_api_route('/customers', customers.on_post, methods=['POST'])
    application.add_api_route('/customers/{customer_key}', customers.on_get, methods=['GET'])
    accounts = AccountResource()
    application.add_api_route('/accounts', accounts.on_post, methods=['POST'])
    application.add_api_route('/accounts', accounts.on_get_list, methods=['GET'])
    application.add_api_route('/accounts/{account_key}', accounts.on_get, methods=['GET'])
    application.add_api_route('/accounts/{account_key}/status', accounts.on_put_status, methods=['PUT'])
    register_error_handlers(application)
    return application


check_variables()
verify_catalog()
setup_logging()
app = create_app()
