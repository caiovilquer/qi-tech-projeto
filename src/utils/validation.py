import re
from datetime import datetime, timezone
from uuid import UUID
from errors import InvalidSchema, BankingError


def uuid_value(value, cursor=False):
    try:
        if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', value):
            raise ValueError()
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        if cursor:
            raise BankingError('QIT001033')
        raise InvalidSchema('UUID required')


def customer_context(request):
    raw = request.headers.get('CUSTOMER-KEY')
    if raw is None:
        raise BankingError('QIT000005')
    return uuid_value(raw)


def idempotency_key(request):
    return uuid_value(request.headers.get('Idempotency-Key'))


def instant(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)', value):
        raise InvalidSchema('RFC3339 timestamp with timezone required')
    try:
        return datetime.fromisoformat(value.upper().replace('Z', '+00:00')).astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise InvalidSchema('Invalid timestamp')


def query(request, allowed):
    if set(request.query_params) - set(allowed) or any(len(request.query_params.getlist(k)) != 1 for k in request.query_params):
        raise InvalidSchema('Unknown or repeated query parameter')
    return dict(request.query_params)


def query_integer(value, lower, upper):
    if not re.fullmatch(r'[0-9]{1,10}', value) or not lower <= int(value) <= upper:
        raise InvalidSchema('Invalid pagination')
    return int(value)
