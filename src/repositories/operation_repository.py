from uuid import uuid4
from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert
import constants
from models import operation, account, account_entry


class OperationRepository:
    def __init__(self, context):
        self.session=context.db_session

    def reserve(self, values):
        return self.session.execute(insert(operation).values(**values,operation_key=str(uuid4()))
                    .on_conflict_do_nothing(index_elements=[operation.c.customer_id,operation.c.idempotency_key])
                    .returning(operation)).mappings().first()

    def replay(self, customer_id, key):
        return self.session.execute(select(operation).where(operation.c.customer_id==customer_id,
                                                           operation.c.idempotency_key==key)).mappings().one()

    def financial_time(self):
        return constants.TEST_CLOCK or self.session.execute(select(func.clock_timestamp())).scalar_one()

    def timestamp(self, operation_id, created_at):
        self.session.execute(update(operation).where(operation.c.id==operation_id).values(created_at=created_at))

    def delta(self, operation_id, account_id, amount, role, created_at):
        balance=self.session.execute(update(account).where(account.c.id==account_id).values(
                      balance_cents=account.c.balance_cents+amount).returning(account.c.balance_cents)).scalar_one()
        self.session.execute(insert(account_entry).values(entry_key=str(uuid4()),operation_id=operation_id,
                account_id=account_id,role=role,delta_cents=amount,balance_after_cents=balance,created_at=created_at))
        return balance

    def detail(self, account_id, key):
        op=self.session.execute(select(operation).where(operation.c.operation_key==key)).mappings().first()
        if op is None:
            return None, []
        entries=self.session.execute(select(account_entry).where(account_entry.c.operation_id==op['id'],
                              account_entry.c.account_id==account_id).order_by(account_entry.c.id)).mappings().all()
        return op, entries

    def statement(self, account_id, limit, cursor, filters):
        conditions=[account_entry.c.account_id==account_id]
        if filters.get('from') is not None: conditions.append(account_entry.c.created_at>=filters['from'])
        if filters.get('to') is not None: conditions.append(account_entry.c.created_at<filters['to'])
        if cursor:
            marker=self.session.execute(select(account_entry.c.id).where(*conditions,account_entry.c.entry_key==cursor)).scalar_one_or_none()
            if marker is None:
                return None
            conditions.append(account_entry.c.id<marker)
        return self.session.execute(select(account_entry,operation.c.operation_key).join(operation,operation.c.id==account_entry.c.operation_id)
                                   .where(*conditions).order_by(account_entry.c.id.desc()).limit(limit+1)).mappings().all()
