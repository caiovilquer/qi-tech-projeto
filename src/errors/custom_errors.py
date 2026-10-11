from errors.base_error import QIException

# One registry is the authority for public banking codes. No raw DB messages.
CATALOG = {
    'QIT000004': (403, 'Monitoring credential required'),
    'QIT000005': (403, 'Customer context required'),
    'QIT001003': (422, 'Invalid document'),
    'QIT001004': (409, 'Document already registered'),
    'QIT001008': (404, 'Customer unavailable'),
    'QIT001009': (404, 'Account unavailable'),
    'QIT001010': (422, 'Origin and destination must differ'),
    'QIT001011': (409, 'Insufficient funds'),
    'QIT001012': (409, 'Idempotency key conflicts with request'),
    'QIT001013': (409, 'Balance ceiling exceeded'),
    'QIT001014': (503, 'Database temporarily unavailable'),
    'QIT001026': (404, 'Destination unavailable'),
    'QIT001027': (503, 'Commit result unknown; recover with same key'),
    'QIT001028': (404, 'Transaction unavailable'),
    'QIT001029': (409, 'Account state prevents operation'),
    'QIT001030': (422, 'Account opening declined'),
    'QIT001031': (503, 'Account opening pending; bureau unavailable'),
    'QIT001032': (409, 'Pix quota exceeded'),
    'QIT001033': (400, 'Cursor unavailable'),
    'QIT001034': (409, 'Account status version conflicts'),
    'QIT001035': (403, 'Sandbox deposits disabled'),
}


class BankingError(QIException):
    def __init__(self, code, account_key=None):
        status, message = CATALOG[code]
        super().__init__('Banking request error', code, status, message, message)
        if account_key is not None and code in ('QIT001030', 'QIT001031'):
            self.details = {'account_key': str(account_key)}


def verify_catalog():
    from errors.base_error import error_verification
    error_verification()
    from errors import InvalidSchema, ForbiddenNotInternal, InvalidParameter, InternalError, MethodNotAllowed, NotFoundResource
    codes = [c.code for c in (InvalidSchema, ForbiddenNotInternal, InvalidParameter, InternalError, MethodNotAllowed, NotFoundResource)] + list(CATALOG)
    if len(set(codes)) != len(codes):
        raise RuntimeError('Duplicate error code')
