# Protótipo bancário QI Tech · RFC v8

API de sandbox para PF/PJ, múltiplas contas de titular único, abertura com bureau
simulado, aportes, transferências INTERNAL e PIX_SIMULATED, estados versionados
e extrato por lançamento. BRL em centavos inteiros. Python 3.11, FastAPI,
SQLAlchemy 2.0, psycopg2 e PostgreSQL 16, preservando as versões diretas da base.

A especificação está disponível em [PDF](docs/RFC-v8.pdf) e
[Markdown editável](docs/RFC-v8.md), com os diagramas em `docs/assets/`.
A [implementação](docs/implementacao.md) descreve a organização do código,
os protocolos de escrita e a execução dos testes.

## Equipe

- Caio Cidade Rodrigues
- Caio Vilquer Carvalho
- Matheus Victor Barbosa dos Santos

## Subir o sandbox

Requisitos: Docker com Compose v2 e Git. Python 3 no host somente para o roteiro
completo de verificação; a API, o PostgreSQL e o pytest rodam em containers Linux.

```bash
docker compose up -d --build --wait
curl http://localhost:3000/
```

Resposta: `{"service":"banking-api"}`. A porta pode ser alterada por `API_PORT`.
PostgreSQL e MockServer são internos à rede Compose; a API publica apenas em
127.0.0.1. A imagem é construída, sem reload/bind mount de código. O volume
`bank-data` persiste entre reinícios. `database/database.sql` inicializa **somente
volume novo**, sem migrar bancos existentes.

Configuração opcional:

```bash
cp .env.example .env
```

Os valores versionados são fictícios e exclusivos do sandbox. `INTERNAL_TOKEN`
e `MONITORING_TOKEN` precisam diferir; não use dados reais. Fora do ambiente
local, HTTPS e segredos externos ao Git são responsabilidade da operação.
`SANDBOX_DEPOSITS=true` habilita explicitamente o aporte; false recusa novos
aportes com QIT001035. Replay de um aporte confirmado recupera o fato original.

O MockServer inicial aprova todos os documentos matematicamente válidos, sem
consulta real. O contrato local é `POST /check` com customer_type/document_number,
respondendo status REGULAR/IRREGULAR/NOT_FOUND, has_debt booleano, reference e
checked_at RFC3339. Os testes configuram expectativas específicas por documento
fictício. Falha HTTP, timeout ou resposta inválida mantém a conta PENDING.

## Usar a API

O integrador confiável autentica com `INTERNAL-TOKEN`. Depois do cadastro, envia
`CUSTOMER-KEY` como contexto declarado. A API sempre autoriza os vínculos de
cliente, conta e lançamento. O integrador autentica os usuários e restringe os
comandos administrativos em seu próprio backend. Não há token pessoal.

Os exemplos abaixo usam vetores fictícios; em um sandbox já populado, um novo
cadastro do mesmo documento retorna conflito. Preserve a chave de cada intenção
para recuperar o resultado, inclusive após perda de resposta.

```bash
curl -s http://localhost:3000/customers \
  -H 'INTERNAL-TOKEN: sandbox-integrator-only' \
  -H 'Idempotency-Key: 00000000-0000-4000-8000-000000000001' \
  -H 'Content-Type: application/json' \
  -d '{"customer_type":"PJ","name":"Empresa fictícia","document_number":"12.ABC.345/01DE-35"}'
```

Copie customer_key para CUSTOMER_UUID e account_key para ACCOUNT_UUID:

```bash
curl -s http://localhost:3000/accounts \
  -H 'INTERNAL-TOKEN: sandbox-integrator-only' \
  -H 'CUSTOMER-KEY: CUSTOMER_UUID' \
  -H 'Idempotency-Key: 00000000-0000-4000-8000-000000000002' \
  -H 'Content-Type: application/json' -d '{"customer_key":"CUSTOMER_UUID"}'

curl -s http://localhost:3000/accounts/ACCOUNT_UUID/deposits \
  -H 'INTERNAL-TOKEN: sandbox-integrator-only' -H 'CUSTOMER-KEY: CUSTOMER_UUID' \
  -H 'Idempotency-Key: 00000000-0000-4000-8000-000000000003' \
  -H 'Content-Type: application/json' -d '{"amount_cents":10000}'

curl -s http://localhost:3000/accounts/ACCOUNT_UUID/transfers \
  -H 'INTERNAL-TOKEN: sandbox-integrator-only' -H 'CUSTOMER-KEY: CUSTOMER_UUID' \
  -H 'Idempotency-Key: 00000000-0000-4000-8000-000000000004' \
  -H 'Content-Type: application/json' \
  -d '{"destination_account_key":"DESTINATION_UUID","amount_cents":1000,"modality":"INTERNAL"}'

curl -s 'http://localhost:3000/accounts/ACCOUNT_UUID/statement?limit=10' \
  -H 'INTERNAL-TOKEN: sandbox-integrator-only' -H 'CUSTOMER-KEY: CUSTOMER_UUID'
```

Destination deve ser outra conta existente, inclusive de outro titular. Novos
UUIDs de Idempotency-Key representam novas intenções; não troque a chave para
recuperar uma operação incerta. Cadastro/abertura usam namespaces separados por
integrador/comando; operações usam uma chave durável por cliente entre todas
as suas contas e modalidades. Não existe expiração em 24 horas.

| Método | Rota | Entrada/sucesso |
| --- | --- | --- |
| POST | /customers | PF/PJ, name, document_number, email opcional; 201 customer_key |
| GET | /customers/{customer_key} | 200 cadastro próprio |
| POST | /accounts | customer_key; 201 account_key/opening_result=APPROVED |
| GET | /accounts | page=0, limit=10; 200 data/page/limit/is_last_page |
| GET | /accounts/{account_key} | 200 saldo, BRL, estado e versão |
| PUT | /accounts/{account_key}/status | ACTIVE/BLOCKED, reason, expected_version; 200 |
| POST | /accounts/{account_key}/deposits | amount_cents; 201 operation_key |
| POST | /accounts/{account_key}/transfers | destino, amount_cents, modality obrigatória; 201 operation_key |
| GET | /accounts/{account_key}/statement | cursor, limit, created_at_from/to; 200 data/limit/next_cursor/is_last_page |
| GET | /accounts/{account_key}/transactions/{operation_key} | 200 entries somente da conta autorizada |

POSTs exigem Idempotency-Key UUID. Todas as rotas da tabela exigem INTERNAL-TOKEN;
exceto POST /customers, exigem CUSTOMER-KEY. JSON estrito recusa campos extras,
strings/booleanos/floats monetários. Textos com NUL ou Unicode inválido retornam
400/QIT000001. Principal 1..2^53−1; saldo/tarifa 0..2^53−1.
CPF/CNPJ são texto, com zeros e letras preservados. CNPJ alfanumérico usa o
[algoritmo oficial da Receita Federal](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/cnpj/manual-dv-cnpj.pdf).

Contas PENDING/REJECTED não movimentam; ACTIVE debita/recebe; BLOCKED recebe,
mas não executa novo débito. Recusa de bureau preserva REJECTED; falha técnica
preserva PENDING e fornece details.account_key. Retome com o mesmo POST/chave.
GET não conclui análise. Uma abertura aprovada pode permanecer bloqueada depois;
seu replay continua retornando APPROVED. Comando de estado exige a versão atual;
reenvio da última transição não duplica evento e tentativa antiga não reaplica
bloqueio após desbloqueio.

| Tarifa em centavos | PF | PJ |
| --- | --- | --- |
| INTERNAL | 200 | 500 |
| PIX_SIMULATED | 0 | 100 |
| Aporte próprio de sandbox | 0 | 0 |

Tarifa depende do titular da origem; destino recebe somente o principal.
PIX_SIMULATED é local: nenhuma integração SPI/DICT ou liquidação externa. Quota
por cliente em America/Sao_Paulo: 1.000.000 de 06h inclusive a 20h exclusive;
100.000 de 20h até 06h do dia seguinte. Todas as contas compartilham a quota;
somente principal enviado consome. Recebimentos não a recompõem. Tarifas/limites
são configuráveis e validados no startup; replay conserva a tarifa original.

Extrato usa entries em ordem decrescente, limit 1..100, cursor entry_key do
último item devolvido e next_cursor=null no fim. Datas RFC3339 com fuso, início
inclusivo/fim exclusivo. Preserve os filtros entre páginas; cursor deve estar
na conta/intervalo autorizados. Não há total, offset ou snapshot conjunto com
saldo/detalhe. O detalhe é completo, em ordem crescente, sem dados da contraparte,
IDs internos, fee_cents global ou chave idempotente.

Erros seguem title/description/translation/code. O catálogo completo está na
[RFC, seção 14](docs/RFC-v8.md#14-catálogo-de-erros-e-respostas-seguras). Recusas
pré-COMMIT desfazem a reserva. QIT001027 significa confirmação desconhecida:
um 503 não prova rollback; reenviar a mesma chave e corpo recupera o resultado.
Consumidores podem fazer quatro reenvios após 0,5/1/2/4 s em timeout/rede/falha
transitória, sem repetir 4xx definitivos nem gerar outra chave para a intenção.

## Testar e reproduzir os ensaios

O roteiro completo cria ou reutiliza **somente o projeto Compose indicado**:

```bash
python3 tools/verify.py --project qit-verification --port 3300
```

Ele constrói imagens, roda pytest, interrompe transporte PostgreSQL, testa
calendário com instantes fixos no startup, replay depois de 24h e alteração de
tarifa, reinicia APIs/banco preservando volume, interrompe banco/bureau, testa
sandbox desabilitado e confere logs. O roteiro fixa as tarifas e quotas da RFC
para os testes, independentemente das personalizações no shell ou `.env`.
A terceira API/proxy existe somente no perfil fault; é parada também em caso
de falha do roteiro. O runner não possui Docker socket.
Os comandos são controlados pelo host, com assertivas de negócio apenas por HTTP.

Para apenas a suíte principal, usando as tarifas e quotas padrão:

```bash
APP_ENV=test TEST_CLOCK=2026-10-11T12:00:00Z \
  docker compose --profile test up -d --build --wait api api-fee0
docker compose --profile test run --rm --no-deps runner
```

`--no-deps` preserva a configuração das APIs iniciadas no passo anterior.
Também é possível `python3 tools/verify.py --suite-only --project qit-tests`.
Os erros públicos têm cenários HTTP explícitos em pytest, conforme a
[matriz de testes de erros](docs/erros-testes.md). As regressões de infraestrutura
da base incluem 403, 404, 405 e acentos, junto das sondas atuais. Falhas de banco,
confirmação de COMMIT e erro inesperado são executadas em etapas do roteiro
completo, porque o host precisa preparar cada falha real antes do pytest.

Não há testes ignorados ou placeholders. A suíte prepara clientes/contas/saldo
pelas rotas, sem importar src ou fazer SQL de negócio. PostgreSQL e HTTP são
reais; MockServer substitui somente o bureau. Concorrência julga a primeira
tentativa, sem retries; recuperação é exercitada separadamente.

O relógio configurável só existe em APP_ENV=test, é usado tanto no timestamp
quanto na quota e exige timezone. Não existe endpoint/cabeçalho para mudá-lo.
Modo normal recusa TEST_CLOCK. api-fee0 usa exatamente a mesma imagem/banco e
quatro tarifas zero; não é outro serviço financeiro.

Resultados executados estão em [docs/validacao.md](docs/validacao.md). O workflow
GitHub Actions está preparado para Ubuntu, com limite de 15 minutos; execução
local em containers Linux não significa que o workflow remoto já rodou.

## Camadas, operação e persistência

Resource/schema adapta e valida HTTP; controller autoriza e coordena transações;
repository executa SQL sem commit; models espelham cinco entidades; DTO filtra a
saída; connector cuida do transporte. O contexto/sessão/middlewares vêm da base.
Os módulos SampleEntity foram substituídos após seu commit de importação intacta.

Escrita financeira: autorização → INSERT ON CONFLICT → SELECT separado no replay
→ cliente para Pix → contas por ID com FOR NO KEY UPDATE → leitura fresca e
instante pós-lock → regras → UPDATE relativo/RETURNING e entries → flush → um
COMMIT → resposta. READ COMMITTED, FKs ON DELETE RESTRICT, sequence CACHE 1.
A sessão é fechada antes do HTTP de bureau e criada de novo para conclusão.
Schema bootstrap pode ser gerado/conferido sem acesso ao banco:

```bash
docker compose run --rm --no-deps --entrypoint python \
  -e PYTHONPATH=/app -v "$PWD/tools/schema.py:/schema.py:ro" api /schema.py
```

| Limite | Configuração |
| --- | --- |
| Pool por processo / overflow | 5 / 0 |
| Espera de pool / conexão PostgreSQL | 3 s / 5 s |
| lock_timeout / statement_timeout | 3 s / 5 s |
| idle_in_transaction_session_timeout | 15 s |
| Bureau conexão / leitura | 3 s / 5 s, sem retry interno |
| Cliente de teste conexão / leitura | 3 s / 30 s |
| Espera de readiness / CI | 90 s / 15 min |

GET /health_check retorna 204 público, indicando processo vivo. GET /readiness
exige somente MONITORING-TOKEN e valida banco/schema (204 ou 503/QIT001014):

```bash
curl -i http://localhost:3000/readiness -H 'MONITORING-TOKEN: sandbox-monitoring-only'
docker compose logs api
```

Logs estruturados incluem request_id, rota, duração, código, operation_key e
resultado confirmado/replay/recusado/desconhecido; não imprimem corpos, documentos,
credenciais ou SQL sensível. Dois processos permitem até dez conexões de pool;
o terceiro processo de teste adiciona até cinco somente no ensaio.

```bash
docker compose restart db api
docker compose down
```

Ambos preservam o volume. Para parar o ambiente de verificação, use o mesmo
nome de projeto:

```bash
docker compose -p qit-verification --profile test --profile fault down
```

Reset **opcional e destrutivo**, exclusivo de dados fictícios descartáveis desse
projeto: acrescente `-v` ao down. Não é migração nem rotina de atualização.
Alterações futuras de schema com dados precisam de migração versionada.

O histórico inicia no commit `493b956c152589d2cea4d6c0023f5133c787e019`, com os 67
arquivos originais do ZIP da Aula 1 conferidos antes de qualquer mudança.
A licença MIT original foi preservada.
