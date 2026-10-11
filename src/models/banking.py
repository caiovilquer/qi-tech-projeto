"""Five SQLAlchemy Core models; queries return fresh projections, never stale ORM balances."""
from sqlalchemy import (Table, Column as C, MetaData, BigInteger, String, DateTime,
                        Boolean, ForeignKey as FK, UniqueConstraint as UQ, CheckConstraint as CK,
                        Identity, text, Index)
from sqlalchemy.dialects.postgresql import UUID, JSONB

metadata = MetaData()
M = 2**53 - 1
STATES = "('PENDING','ACTIVE','REJECTED','BLOCKED')"


def pk():
    return C('id', BigInteger, Identity(cache=1), primary_key=True)


def key(name):
    return C(name, UUID(as_uuid=False), nullable=False, unique=True)


def fk(name, target, nullable=False):
    return C(name, BigInteger, FK(target + '.id', ondelete='RESTRICT'), nullable=nullable)


def created():
    return C('created_at', DateTime(timezone=True), nullable=False, server_default=text('clock_timestamp()'))


def creation():
    return [C('creation_integrator', String(120), nullable=False),
            C('creation_idempotency_key', UUID(as_uuid=False), nullable=False),
            C('creation_request', JSONB, nullable=False),
            UQ('creation_integrator', 'creation_idempotency_key')]

customer = Table('customer', metadata, pk(), key('customer_key'),
    C('customer_type', String(2), nullable=False), C('document_number', String(14), nullable=False),
    C('name', String(120), nullable=False), C('email', String(254)), *creation(), created(),
    UQ('customer_type', 'document_number'), CK("customer_type IN ('PF','PJ')"),
    CK("length(trim(name)) > 0"), CK("(customer_type='PF' AND document_number ~ '^[0-9]{11}$') OR (customer_type='PJ' AND document_number ~ '^[A-Z0-9]{12}[0-9]{2}$')"))
account = Table('account', metadata, pk(), key('account_key'), fk('customer_id', 'customer'),
    C('balance_cents', BigInteger, nullable=False, server_default='0'),
    C('status', String(8), nullable=False), C('status_version', BigInteger, nullable=False),
    *creation(), created(), CK(f'balance_cents BETWEEN 0 AND {M}'),
    CK(f'status IN {STATES}'), CK('status_version > 0'),
    CK("status NOT IN ('PENDING','REJECTED') OR balance_cents=0"))
account_status_event = Table('account_status_event', metadata, pk(), key('event_key'), fk('account_id','account'),
    C('version', BigInteger, nullable=False), C('previous_status', String(8)),
    C('new_status', String(8), nullable=False), C('reason', String(240), nullable=False),
    C('actor', String(120), nullable=False), created(), C('bureau_reference', String(120)),
    C('bureau_checked_at', DateTime(timezone=True)), C('has_debt', Boolean),
    UQ('account_id','version'), CK('version > 0'), CK(f'new_status IN {STATES}'),
    CK(f'previous_status IS NULL OR previous_status IN {STATES}'),
    CK("(version=1 AND previous_status IS NULL AND new_status='PENDING') OR (version>1 AND previous_status IS NOT NULL)"),
    CK("length(trim(reason)) > 0"),
    CK("(previous_status IS NOT NULL AND previous_status='PENDING' AND new_status IN ('ACTIVE','REJECTED') AND bureau_reference IS NOT NULL AND bureau_checked_at IS NOT NULL AND has_debt IS NOT NULL) OR ((previous_status IS NULL OR previous_status<>'PENDING') AND bureau_reference IS NULL AND bureau_checked_at IS NULL AND has_debt IS NULL)"))
operation = Table('operation', metadata, pk(), key('operation_key'), fk('customer_id','customer'),
    C('type',String(8),nullable=False), C('modality',String(13)),
    fk('origin_account_id','account',True), fk('destination_account_id','account'),
    C('amount_cents',BigInteger,nullable=False), C('fee_cents',BigInteger,nullable=False),
    C('idempotency_key',UUID(as_uuid=False),nullable=False), created(), UQ('customer_id','idempotency_key'),
    CK(f'amount_cents BETWEEN 1 AND {M}'), CK(f'fee_cents BETWEEN 0 AND {M}'),
    CK("(type='DEPOSIT' AND modality IS NULL AND origin_account_id IS NULL AND fee_cents=0) OR (type='TRANSFER' AND modality IS NOT NULL AND modality IN ('INTERNAL','PIX_SIMULATED') AND origin_account_id IS NOT NULL AND origin_account_id<>destination_account_id)"))
account_entry = Table('account_entry', metadata, pk(), key('entry_key'),
    fk('operation_id','operation'), fk('account_id','account'), C('role',String(16),nullable=False),
    C('delta_cents',BigInteger,nullable=False), C('balance_after_cents',BigInteger,nullable=False), created(),
    UQ('operation_id','role'), CK(f'balance_after_cents BETWEEN 0 AND {M}'),
    CK(f'delta_cents BETWEEN -{M} AND {M} AND delta_cents<>0'),
    CK("(role IN ('DEPOSIT_CREDIT','TRANSFER_CREDIT') AND delta_cents>0) OR (role IN ('TRANSFER_DEBIT','FEE_DEBIT') AND delta_cents<0)"))
Index('account_customer_id_id', account.c.customer_id, account.c.id)
Index('entry_account_id_id', account_entry.c.account_id, account_entry.c.id.desc())
Index('operation_customer_modality_created', operation.c.customer_id, operation.c.modality, operation.c.created_at)
Index('operation_origin', operation.c.origin_account_id)
Index('operation_destination', operation.c.destination_account_id)
Index('entry_operation', account_entry.c.operation_id)
