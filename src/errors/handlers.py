from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from errors.base_error import (
    QIException,
    InternalError,
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
        # Existem duas validacoes neste projeto, nao uma. A query string e
        # os cabecalhos sao julgados antes do controller, em
        # utils/validation.py: um ?page=-3 morre la, com 400 QIT000001. Os
        # parametros de endereco sao todos `str`, que nao tem como falhar.
        #
        # Sobra para o FastAPI o corpo que nem chega a ser um objeto JSON
        # (sintaxe invalida, lista, corpo vazio). A resposta nao repete a
        # mensagem dele, que pode ecoar o conteudo recebido. O QIT000010
        # vem de outro lugar: do controller do extrato, quando
        # created_at_from >= created_at_to.
        return qi_exception_to_response(InvalidSchema("Invalid request format"))

    @application.exception_handler(Exception)
    def handle_unexpected_error(request: Request, exception: Exception) -> JSONResponse:
        return unexpected_error_to_response(request, exception)
