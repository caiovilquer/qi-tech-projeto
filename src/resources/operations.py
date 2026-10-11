from fastapi import Request
from fastapi.responses import JSONResponse
from controllers.operation_controller import OperationController
from utils.schema_handler import SchemaHandler
from utils.validation import uuid_value, customer_context, idempotency_key, query, query_integer


class OperationResource:
    @SchemaHandler.validate('post_deposit.json')
    def on_post_deposit(self, request: Request, account_key: str, payload: dict):
        return JSONResponse(OperationController().write(uuid_value(account_key),customer_context(request),payload,
                            idempotency_key(request),'DEPOSIT'),status_code=201)

    @SchemaHandler.validate('post_transfer.json')
    def on_post_transfer(self, request: Request, account_key: str, payload: dict):
        payload=dict(payload,destination_account_key=uuid_value(payload['destination_account_key']))
        return JSONResponse(OperationController().write(uuid_value(account_key),customer_context(request),payload,
                            idempotency_key(request),'TRANSFER'),status_code=201)

    def on_get_detail(self, request: Request, account_key: str, operation_key: str):
        return JSONResponse(OperationController().detail(uuid_value(account_key),customer_context(request),uuid_value(operation_key)))

    def on_get_statement(self, request: Request, account_key: str):
        params=query(request,['limit','cursor','created_at_from','created_at_to'])
        return JSONResponse(OperationController().statement(uuid_value(account_key),customer_context(request),
              query_integer(params.get('limit','10'),1,100),params.get('cursor'),
              {'from':params.get('created_at_from'),'to':params.get('created_at_to')}))
