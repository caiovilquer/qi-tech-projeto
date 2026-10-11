import json
import time
from fastapi import FastAPI, Request
from constants import BYPASS_ENDPOINTS
from utils.logger import get_logger
from utils.request_context import get_request_id
from errors.handlers import unexpected_error_to_response

logger = get_logger(__name__)


def register_request_logger_middleware(application: FastAPI) -> None:
    @application.middleware('http')
    async def log_request(request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exception:
            response = unexpected_error_to_response(request, exception)
        if request.url.path not in BYPASS_ENDPOINTS:
            context = getattr(request.state, 'banking_context', None)
            logger.info(json.dumps({
                'request_id': get_request_id(),
                'route': request.scope.get('route').path if request.scope.get('route') else request.url.path,
                'duration_ms': round((time.perf_counter()-started)*1000, 2),
                'status': response.status_code,
                'code': getattr(context, 'error_code', None),
                'operation_key': getattr(context, 'operation_key', None),
                'result': getattr(context, 'outcome', 'recusado' if response.status_code >= 400 else 'consultado'),
            }))
        return response
