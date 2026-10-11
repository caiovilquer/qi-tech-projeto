"""CPF and CNPJ numeric/alphanumeric. Receita Federal: ASCII-48, modulo 11.
https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/cnpj/manual-dv-cnpj.pdf
"""
import re
from errors import InvalidSchema, BankingError


def normalize_document(kind, raw):
    pattern = (r'(?:[0-9]{11}|[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2})' if kind == 'PF' else
               r'(?:[A-Za-z0-9]{12}[0-9]{2}|[A-Za-z0-9]{2}\.[A-Za-z0-9]{3}\.[A-Za-z0-9]{3}/[A-Za-z0-9]{4}-[0-9]{2})')
    if not isinstance(raw, str) or not re.fullmatch(pattern, raw):
        raise InvalidSchema('Invalid document format')
    document = raw.translate(str.maketrans('', '', '.-/')).upper()
    if len(set(document)) == 1:
        raise BankingError('QIT001003')
    prefix = document[:-2]
    for n in range(2):
        if kind == 'PF':
            weights = list(range(len(prefix)+1, 1, -1))
        else:
            weights = [5,4,3,2,9,8,7,6,5,4,3,2] if n == 0 else [6,5,4,3,2,9,8,7,6,5,4,3,2]
        remainder = sum((ord(c)-48)*w for c,w in zip(prefix, weights)) % 11
        digit = 0 if remainder < 2 else 11-remainder
        prefix += str(digit)
    if prefix != document:
        raise BankingError('QIT001003')
    return document
