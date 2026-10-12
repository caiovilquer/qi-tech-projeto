from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from errors.base_error import (
    QIException,
    InternalError,
    InvalidParameter,
    InvalidSchema,
    MethodNotAllowed,
    NotFoundResource,
)
from utils.logger import get_logger


logger = get_logger(__name__)


def qi_exception_to_response(exception: QIException) -> JSONResponse:
    """Traduz um erro nosso para a resposta JSON que o cliente recebe.

    Este é o único lugar do projeto que sabe como um erro vira HTTP.
    Trocar de framework significa reescrever esta função — e mais nada.
    """
    body = {
        "title": exception.title,
        "description": exception.description,
        "translation": exception.translation,
        "code": exception.code,
    }
    if hasattr(exception, "details"):
        body["details"] = exception.details
    from database import get_context
    try:
        context = get_context()
        context.error_code = exception.code
        context.outcome = "desconhecido" if exception.code in ("QIT001027", "QIT000500") else "recusado"
    except Exception:
        pass
    return JSONResponse(status_code=exception.http_status, content=body)


def unexpected_error_to_response(request: Request, exception: Exception) -> JSONResponse:
    # Keep the response and structured request log inside the request-id layer.
    # A 500 does not prove rollback, so retain uncertainty for key recovery.
    context = getattr(request.state, "banking_context", None)
    if context is not None:
        context.error_code = "QIT000500"
        context.outcome = "desconhecido"
    logger.error("Unexpected failure (%s)", type(exception).__name__)
    return qi_exception_to_response(InternalError())


def describe_validation_error(error: dict) -> str:
    location = []
    for part in error.get("loc", []):
        if part not in ("body", "query"):
            location.append(str(part))

    message = error.get("msg", "invalid value")

    if location:
        return f"{message} in {'.'.join(location)}"

    return message


def register_error_handlers(application: FastAPI) -> None:
    """Ensina a aplicação a responder cada tipo de erro."""

    @application.exception_handler(QIException)
    def handle_qi_exception(request: Request, exception: QIException) -> JSONResponse:
        return qi_exception_to_response(exception)

    @application.exception_handler(StarletteHTTPException)
    def handle_http_exception(request: Request, exception: StarletteHTTPException) -> JSONResponse:
        if exception.status_code == 400:
            # FastAPI reports undecodable request bodies as HTTPException(400).
            # This is a client format error, including invalid UTF-8 JSON.
            return qi_exception_to_response(InvalidSchema("Invalid request format"))

        if exception.status_code == 404:
            return qi_exception_to_response(NotFoundResource())

        if exception.status_code == 405:
            return qi_exception_to_response(MethodNotAllowed())

        logger.error(f"HTTP {exception.status_code} em {request.url.path}: {exception.detail}")
        return qi_exception_to_response(InternalError())

    @application.exception_handler(RequestValidationError)
    def handle_validation_error(request: Request, exception: RequestValidationError) -> JSONResponse:
        errors = exception.errors()

        if errors:
            first_error = errors[0]
        else:
            first_error = {}

        description = describe_validation_error(first_error)
        origin = first_error.get("loc", [""])[0]

        # Este ramo NAO e alcancado hoje, e vale saber por que — e a
        # unica pista de que existem duas validacoes neste projeto, nao
        # uma.
        #
        # Quem julga a query string aqui sao os resources, com query() e
        # query_integer() de utils/validation.py, antes do FastAPI. Um
        # ?page=-3 morre la, com 400 QIT000001 — nunca chega a virar
        # RequestValidationError. E os parametros de endereco sao todos
        # `str`, que nao tem como falhar validacao.
        #
        # O ramo fica de pe para o dia em que alguma rota declarar um
        # parametro tipado (page: int) e passar a depender do FastAPI
        # para isso. O QIT000010 que o cliente ve hoje vem de outro
        # lugar: do controller do extrato, quando created_at_from nao
        # precede created_at_to.
        if origin in ("query", "path"):
            return qi_exception_to_response(InvalidSchema("Invalid request format"))

        return qi_exception_to_response(InvalidSchema("Invalid request format"))

    @application.exception_handler(Exception)
    def handle_unexpected_error(request: Request, exception: Exception) -> JSONResponse:
        return unexpected_error_to_response(request, exception)
