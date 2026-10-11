from fastapi import Request
from fastapi.responses import JSONResponse
from controllers.account_controller import AccountController
from utils.schema_handler import SchemaHandler
from utils.validation import uuid_value, customer_context, idempotency_key, query, query_integer


class AccountResource:
    @SchemaHandler.validate('post_account.json')
    def on_post(self, request: Request, payload: dict):
        payload={'customer_key':uuid_value(payload['customer_key'])}
        return JSONResponse(AccountController().open(payload,customer_context(request),idempotency_key(request)),status_code=201)

    def on_get(self, request: Request, account_key: str):
        return JSONResponse(AccountController().get(uuid_value(account_key),customer_context(request)))

    def on_get_list(self, request: Request):
        params=query(request,['page','limit'])
        return JSONResponse(AccountController().list(customer_context(request),query_integer(params.get('page','0'),0,999999999),
                                                    query_integer(params.get('limit','10'),1,100)))

    @SchemaHandler.validate('put_status.json')
    def on_put_status(self, request: Request, account_key: str, payload: dict):
        return JSONResponse(AccountController().status(uuid_value(account_key),customer_context(request),payload))
