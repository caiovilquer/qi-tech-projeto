from uuid import uuid4
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from models import account, account_status_event
from constants import INTEGRATOR_ID


class AccountRepository:
    def __init__(self, context):
        self.session = context.db_session

    def create(self, customer_id, payload, key):
        return self.session.execute(insert(account).values(account_key=str(uuid4()),customer_id=customer_id,
            status='PENDING',status_version=1,balance_cents=0,creation_integrator=INTEGRATOR_ID,
            creation_idempotency_key=key,creation_request=payload).on_conflict_do_nothing(
                index_elements=[account.c.creation_integrator,account.c.creation_idempotency_key]).returning(account)).mappings().first()

    def creation(self, key):
        return self.session.execute(select(account).where(account.c.creation_integrator==INTEGRATOR_ID,
                account.c.creation_idempotency_key==key)).mappings().first()

    def by_key(self, key):
        return self.session.execute(select(account).where(account.c.account_key==key)).mappings().first()

    def lock(self, ids):
        # key_share=True, read=False compiles to FOR NO KEY UPDATE in PostgreSQL.
        return self.session.execute(select(account).where(account.c.id.in_(ids)).order_by(account.c.id)
                                    .with_for_update(key_share=True)).mappings().all()

    def event(self, row, previous, reason, actor, bureau=None):
        values = dict(event_key=str(uuid4()),account_id=row['id'],version=row['status_version'],
                      previous_status=previous,new_status=row['status'],reason=reason,actor=actor)
        if bureau is not None:
            values.update(bureau_reference=bureau['reference'],bureau_checked_at=bureau['checked_at'],has_debt=bureau['has_debt'])
        self.session.execute(insert(account_status_event).values(**values))

    def change(self, row, status, reason, actor, bureau=None):
        changed = self.session.execute(update(account).where(account.c.id==row['id']).values(
                status=status,status_version=account.c.status_version+1).returning(account)).mappings().one()
        self.event(changed, row['status'], reason, actor, bureau)
        return changed

    def last_event(self, account_id):
        return self.session.execute(select(account_status_event).where(account_status_event.c.account_id==account_id)
                        .order_by(account_status_event.c.version.desc()).limit(1)).mappings().one()

    def opening_event(self, account_id):
        return self.session.execute(select(account_status_event).where(account_status_event.c.account_id==account_id,
                                 account_status_event.c.previous_status=='PENDING')).mappings().one()

    def list(self, customer_id, page, limit):
        return self.session.execute(select(account).where(account.c.customer_id==customer_id).order_by(account.c.id)
                        .offset(page*limit).limit(limit+1)).mappings().all()
