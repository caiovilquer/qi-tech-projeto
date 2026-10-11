from datetime import datetime, timezone


def utc(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def customer_dto(row):
    return {k: (utc(row[k]) if k == 'created_at' else row[k])
            for k in ['customer_key','customer_type','document_number','name','email','created_at']}


def account_dto(row, customer_key):
    return {k: row[k] for k in ['account_key','balance_cents','status','status_version']} | {'customer_key':customer_key, 'currency':'BRL'}
