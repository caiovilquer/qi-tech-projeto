from datetime import timezone


def utc(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def customer_dto(row):
    return {k: (utc(row[k]) if k == 'created_at' else row[k])
            for k in ['customer_key','customer_type','document_number','name','email','created_at']}


def account_dto(row, customer_key):
    return {k: row[k] for k in ['account_key','balance_cents','status','status_version']} | {'customer_key':customer_key, 'currency':'BRL'}


def operation_detail_dto(op, account_key, entries):
    return {
        'operation_key': op['operation_key'], 'account_key': account_key,
        'type': op['type'], 'modality': op['modality'], 'currency': 'BRL',
        'created_at': utc(op['created_at']),
        'entries': [{k: row[k] for k in ['entry_key', 'role', 'delta_cents', 'balance_after_cents']}
                    for row in entries],
    }


def statement_dto(rows, limit):
    data = [{k: (utc(row[k]) if k == 'created_at' else row[k])
             for k in ['entry_key', 'operation_key', 'role', 'delta_cents', 'balance_after_cents', 'created_at']}
            for row in rows[:limit]]
    return {'data': data, 'limit': limit,
            'next_cursor': data[-1]['entry_key'] if len(rows) > limit else None,
            'is_last_page': len(rows) <= limit}
