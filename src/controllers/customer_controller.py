from controllers.base_controller import BaseController
from controllers.transaction import db_action, commit
from repositories.customer_repository import CustomerRepository
from dtos.banking_dto import customer_dto
from errors import BankingError, InvalidSchema
from utils.document_number import normalize_document


class CustomerController(BaseController):
    def __init__(self):
        super().__init__('customers')
        self.repository = CustomerRepository(self.context)

    def authorize(self, key):
        row = self.repository.by_key(key)
        if row is None:
            raise BankingError('QIT001008')
        return row

    @db_action
    def create(self, payload, key):
        normalized = dict(payload, name=payload['name'].strip(), email=payload.get('email'),
                          document_number=normalize_document(payload['customer_type'],payload['document_number']))
        if not 1 <= len(normalized['name']) <= 120:
            raise InvalidSchema('Name must contain 1 to 120 characters')
        row = self.repository.create(normalized, key)
        if row is None:
            # Separate command sees the winner after ON CONFLICT waits.
            row = self.repository.creation(key)
            if row is None:
                raise BankingError('QIT001004')
            if row['creation_request'] != normalized:
                raise BankingError('QIT001012')
            self.context.outcome = 'replay'
            self.session.rollback()
        else:
            commit(self)
        return {'customer_key': row['customer_key']}

    @db_action
    def get(self, key, context_key):
        if key != context_key:
            raise BankingError('QIT001008')
        return customer_dto(self.authorize(context_key))
