from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from models import customer
from constants import INTEGRATOR_ID


class CustomerRepository:
    def __init__(self, context):
        self.session = context.db_session

    def create(self, payload, key):
        values = dict(payload, customer_key=str(uuid4()), creation_integrator=INTEGRATOR_ID,
                      creation_idempotency_key=key, creation_request=payload)
        return self.session.execute(insert(customer).values(**values).on_conflict_do_nothing().returning(customer)).mappings().first()

    def creation(self, key):
        return self.session.execute(select(customer).where(customer.c.creation_integrator == INTEGRATOR_ID,
                                       customer.c.creation_idempotency_key == key)).mappings().first()

    def by_key(self, key):
        return self.session.execute(select(customer).where(customer.c.customer_key == key)).mappings().first()
