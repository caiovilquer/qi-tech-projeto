from fastapi import Request
from fastapi.responses import JSONResponse
from controllers.customer_controller import CustomerController
from utils.schema_handler import SchemaHandler
from utils.validation import uuid_value, customer_context, idempotency_key


class CustomerResource:
    @SchemaHandler.validate('post_customer.json')
    def on_post(self, request: Request, payload: dict):
        return JSONResponse(CustomerController().create(payload, idempotency_key(request)), status_code=201)

    def on_get(self, request: Request, customer_key: str):
        return JSONResponse(CustomerController().get(uuid_value(customer_key), customer_context(request)))
