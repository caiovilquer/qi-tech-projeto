import secrets
from fastapi import FastAPI, Request
from constants import BYPASS_ENDPOINTS, INTERNAL_TOKEN, MONITORING_TOKEN
from errors import ForbiddenNotInternal, BankingError
from errors.handlers import qi_exception_to_response


def register_internal_token_middleware(application: FastAPI) -> None:
    @application.middleware('http')
    async def check_internal_token(request: Request, call_next):
        if request.url.path in BYPASS_ENDPOINTS:
            return await call_next(request)
        if request.url.path == '/readiness':
            valid = secrets.compare_digest(request.headers.get('MONITORING-TOKEN', '').encode(), MONITORING_TOKEN.encode())
            error = BankingError('QIT000004')
        else:
            valid = secrets.compare_digest(request.headers.get('INTERNAL-TOKEN', '').encode(), INTERNAL_TOKEN.encode())
            error = ForbiddenNotInternal()
        if not valid:
            return qi_exception_to_response(error)
        return await call_next(request)
