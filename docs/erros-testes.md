# Testes dos erros públicos

Os 27 códigos registrados possuem cenários HTTP em pytest. Esta matriz descreve
comportamentos verificados; não é uma medição de cobertura de linhas. A suíte
prepara dados pelas rotas, usa PostgreSQL real e não importa código de `src`.

Os testes em `integration/` rodam na suíte principal. `fault_transport.py` e
`operational_errors.py` são executados explicitamente pelo host em etapas do
roteiro `tools/verify.py`, pois exigem falhas controladas. Não há skips ou mocks
de regras, sessões ou banco. O MockServer representa somente o bureau externo.

| Código | HTTP | Cenário pytest |
| --- | --- | --- |
| QIT000001 | 400 | JSON inválido, UTF-8 inválido, NUL e surrogates isolados em textos, campos extras, valores monetários não inteiros, UUIDs e estados inválidos; [test_errors.py](../tests/integration/test_errors.py) e testes de contratos |
| QIT000002 | 403 | Token interno ausente/incorreto, inclusive antes do roteamento; [test_health.py](../tests/integration/test_health.py) |
| QIT000004 | 403 | Readiness sem credencial de monitoramento válida; [test_health.py](../tests/integration/test_health.py) |
| QIT000005 | 403 | Contexto de cliente ausente; [test_customers.py](../tests/integration/test_customers.py) |
| QIT000010 | 400 | Intervalo temporal vazio/invertido com datas válidas; [test_queries.py](../tests/integration/test_queries.py) |
| QIT000404 | 404 | Rota ausente com token válido, mantendo envelope da base; [test_health.py](../tests/integration/test_health.py) |
| QIT000405 | 405 | Método não permitido em rota pública; [test_health.py](../tests/integration/test_health.py) |
| QIT000500 | 500 | Arquivo de schema ausente na API de teste: envelope seguro, request_id e ausência de dados internos; [operational_errors.py](../tests/operational_errors.py) |
| QIT001003 | 422 | CPF com dígitos repetidos ou com o primeiro ou o segundo dígito verificador errado, e CNPJ alfanumérico com dígito verificador errado; [test_customers.py](../tests/integration/test_customers.py) |
| QIT001004 | 409 | Documento duplicado, inclusive criação concorrente; [test_customers.py](../tests/integration/test_customers.py) |
| QIT001008 | 404 | Cliente ausente usado como contexto ([test_errors.py](../tests/integration/test_errors.py)), abertura para cliente fora do contexto ([test_accounts.py](../tests/integration/test_accounts.py)) e leitura de cadastro alheio ([test_customers.py](../tests/integration/test_customers.py)) |
| QIT001009 | 404 | Conta ausente ou alheia, com corpos de resposta comparados e idênticos; [test_accounts.py](../tests/integration/test_accounts.py) |
| QIT001010 | 422 | Origem igual ao destino; [test_money.py](../tests/integration/test_money.py) |
| QIT001011 | 409 | Saldo insuficiente para principal e tarifa, sem efeitos; [test_money.py](../tests/integration/test_money.py) |
| QIT001012 | 409 | Mesma chave com intenção diferente, sem alterar o fato original; testes de clientes, contas, dinheiro e Pix |
| QIT001013 | 409 | Crédito acima do teto, por aporte e por transferência, preservando saldos e históricos de origem e destino; [test_money.py](../tests/integration/test_money.py) |
| QIT001014 | 503 | Banco parado e escrita interrompida antes do COMMIT; [operational_errors.py](../tests/operational_errors.py) e [fault_transport.py](../tests/fault_transport.py) |
| QIT001026 | 404 | Destino inexistente; [test_money.py](../tests/integration/test_money.py) |
| QIT001027 | 503 | Confirmação de COMMIT descartada depois de o banco confirmar: mesma chave recupera sem novo débito; [fault_transport.py](../tests/fault_transport.py) |
| QIT001028 | 404 | Operação existente sem lançamento na conta autorizada ([test_queries.py](../tests/integration/test_queries.py)) e operação inexistente ([test_money.py](../tests/integration/test_money.py)) |
| QIT001029 | 409 | Estado impede a ação; PENDING/REJECTED sem movimentação e BLOCKED sem novo débito; testes de contas e dinheiro |
| QIT001030 | 422 | Bureau irregular/não encontrado recusa abertura, preservando conta e chave próprias; [test_accounts.py](../tests/integration/test_accounts.py) |
| QIT001031 | 503 | Bureau indisponível, malformado, referência com NUL/Unicode inválido ou timeout mantém PENDING e permite retomada da mesma conta; [test_accounts.py](../tests/integration/test_accounts.py) |
| QIT001032 | 409 | Quota Pix compartilhada insuficiente; [test_pix.py](../tests/integration/test_pix.py) e ensaios de calendário |
| QIT001033 | 400 | Cursor inválido, alheio ou fora do intervalo; [test_queries.py](../tests/integration/test_queries.py) |
| QIT001034 | 409 | Versão obsoleta e comandos administrativos concorrentes incompatíveis; testes de contas e consultas |
| QIT001035 | 403 | Sandbox desabilitado recusa aporte sem mudar saldo/histórico; [operational_errors.py](../tests/operational_errors.py) |

## Falhas observadas antes das correções

- O teste de 500 falhou porque `X-Request-ID` não voltava na resposta. O
  tratamento da exceção agora permanece dentro da camada de correlação/log,
  retorna o envelope seguro e registra resultado desconhecido.
- O teste de corpo JSON com UTF-8 inválido recebeu 500. A exceção HTTP 400 do
  parser agora vira `400/QIT000001`, sem expor bytes ou detalhes internos.
- NUL e surrogates Unicode isolados em nome, email e motivo chegavam ao banco
  e produziam 500. A validação agora retorna `400/QIT000001`, preservando chave,
  estado e versão; acentos e emojis válidos continuam aceitos.
- Uma referência de bureau com NUL produzia 500 sem `details.account_key`.
  Referências inválidas agora retornam `503/QIT001031`, mantendo PENDING e
  permitindo a retomada pelo mesmo POST/chave.

Esses cenários são reproduzidos pelo roteiro `tools/verify.py`. No ensaio de
schema ausente, a instrumentação altera somente o container descartável
`api-fault` e restaura o arquivo ao final.
O controle das falhas fica no host, sem endpoint de instrumentação na API e sem
Docker socket no runner.

## Garantias de infraestrutura da base

A suíte preserva os comportamentos dos seis testes de infraestrutura originais:
raiz 200, liveness 204, token ausente 403, rota ausente 404, método indevido 405
e acentos nas traduções de erros. Os contratos atuais da RFC são conferidos
junto dessas garantias, incluindo o nome `banking-api` e readiness separada.
As verificações relacionadas a `SampleEntity` não fazem parte do domínio bancário.
