from errors.base_error import QIException

# One registry is the authority for public banking codes. No raw DB messages.
# Entries are a tuple, not a dict literal: a repeated key in a dict literal
# silently replaces the earlier entry, so verify_catalog() could never see it.
# translation follows the base convention: the Portuguese text of description.
ENTRIES = (
    ('QIT000004', 403, 'Monitoring credential required', 'Credencial de monitoramento obrigatória'),
    ('QIT000005', 403, 'Customer context required', 'Contexto do cliente obrigatório'),
    ('QIT001003', 422, 'Invalid document', 'Documento inválido'),
    ('QIT001004', 409, 'Document already registered', 'Documento já cadastrado'),
    ('QIT001008', 404, 'Customer unavailable', 'Cliente indisponível'),
    ('QIT001009', 404, 'Account unavailable', 'Conta indisponível'),
    ('QIT001010', 422, 'Origin and destination must differ', 'Origem e destino precisam ser diferentes'),
    ('QIT001011', 409, 'Insufficient funds', 'Saldo insuficiente'),
    ('QIT001012', 409, 'Idempotency key conflicts with request', 'A chave de idempotência já foi usada com outro pedido'),
    ('QIT001013', 409, 'Balance ceiling exceeded', 'Teto de saldo excedido'),
    ('QIT001014', 503, 'Database temporarily unavailable', 'Banco de dados temporariamente indisponível'),
    ('QIT001026', 404, 'Destination unavailable', 'Destino indisponível'),
    ('QIT001027', 503, 'Commit result unknown; recover with same key',
     'Resultado da confirmação desconhecido; recupere com a mesma chave'),
    ('QIT001028', 404, 'Transaction unavailable', 'Transação indisponível'),
    ('QIT001029', 409, 'Account state prevents operation', 'O estado da conta impede a operação'),
    ('QIT001030', 422, 'Account opening declined', 'Abertura de conta recusada'),
    ('QIT001031', 503, 'Account opening pending; bureau unavailable', 'Abertura de conta pendente; bureau indisponível'),
    ('QIT001032', 409, 'Pix quota exceeded', 'Quota de Pix excedida'),
    ('QIT001033', 400, 'Cursor unavailable', 'Cursor indisponível'),
    ('QIT001034', 409, 'Account status version conflicts', 'A versão do estado da conta não confere'),
    ('QIT001035', 403, 'Sandbox deposits disabled', 'Aportes de sandbox desabilitados'),
)
CATALOG = {code: (status, description, translation) for code, status, description, translation in ENTRIES}


class BankingError(QIException):
    def __init__(self, code, account_key=None):
        status, description, translation = CATALOG[code]
        super().__init__('Banking request error', code, status, description, translation)
        if account_key is not None and code in ('QIT001030', 'QIT001031'):
            self.details = {'account_key': str(account_key)}


def verify_catalog():
    from errors.base_error import error_verification
    error_verification()
    from errors import InvalidSchema, ForbiddenNotInternal, InvalidParameter, InternalError, MethodNotAllowed, NotFoundResource
    codes = [c.code for c in (InvalidSchema, ForbiddenNotInternal, InvalidParameter, InternalError, MethodNotAllowed, NotFoundResource)]
    codes += [entry[0] for entry in ENTRIES]
    if len(set(codes)) != len(codes):
        raise RuntimeError('Duplicate error code')
