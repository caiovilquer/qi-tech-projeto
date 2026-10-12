# Organização da API bancária

A implementação conserva o caminho da base da Aula 1:

```text
HTTP → middlewares → resource/schema → controller → repository/model → PostgreSQL
                                         ↓
                                        DTO → resposta
```

- `app.py` registra endereços explícitos e handlers síncronos.
- `resources/` adapta UUIDs, cabeçalhos, queries e JSON, sem SQL de negócio.
- `schemas/` guarda contratos JSON Schema estritos; `utils/schema_handler.py`
  especializa integer para recusar 1.0, strings e booleanos monetários, e string
  para recusar NUL e Unicode inválido. O validador estende o Draft 7; a base usava
  o padrão de `jsonschema.validate` (Draft 2020-12), e os schemas atuais não usam
  palavra-chave que mude entre os dois.
- Erros públicos seguem o envelope da base (description em inglês, translation em
  português); `errors/custom_errors.py` recusa código repetido na inicialização.
- `controllers/` autoriza os vínculos, aplica regras e coordena commit/rollback.
- `repositories/` executa INSERT, SELECT, locks e UPDATE; nunca faz commit.
- `models/banking.py` espelha as cinco tabelas via SQLAlchemy Core; leituras
  são projeções frescas, sem cache ORM que possa sobrescrever saldo antigo.
- `dtos/banking_dto.py` expõe apenas campos permitidos, sobretudo no detalhe
  de uma operação recebida pelo destinatário.
- `connectors/bureau_connector.py` encapsula transporte, contrato e timeouts
  externos; decisão de aprovação permanece no controller.
- `database.py` e `middlewares/session_manager.py` mantêm o contexto de sessão
  da base: controller pede sob demanda, middleware fecha sempre e não comita.
- `middlewares/` acrescenta request_id, logs sanitizados e credenciais distintas
  para negócio/readiness. Contexto carrega a classificação do resultado.

O controller fecha e retira a sessão do contexto antes de chamar bureau; cria
nova sessão depois do HTTP para coordenar conclusão. PENDING é persistência
cadastral, sem reserva monetária durável pendente.

`controllers/transaction.py` separa flush pré-COMMIT da chamada commit. Falha de
banco/pool antes dessa fronteira usa QIT001014; falha na confirmação usa
QIT001027 e conserva a incerteza. DTOs de sucesso ficam prontos antes de comitar.

Financeiro arbitra chave por INSERT ON CONFLICT; SELECT de replay é comando
separado em READ COMMITTED. Pix coordena cliente antes de contas. Contas usam
FOR NO KEY UPDATE por ID crescente; UPDATE relativo/RETURNING alimenta cada
entry, sob lock. Repositories não pré-alocam IDs nem guardam saldo absoluto.

O schema inicial vem de `database/database.sql`; `tools/schema.py` permite
conferir sua correspondência com models sem conectar ao banco. Bootstrap é
somente para volume novo, conforme a RFC; evolução com dados requer migração.

`tests/integration/` usa pytest/HTTP e setup pelas rotas. `tests/scenarios.py`
implementa ensaios de reinício/calendário acionados pelo host. O proxy em
`tools/postgres_proxy.py` é instrumento opcional de teste, sem código de negócio
nem consultas de regra ao banco. `tools/verify.py` controla somente o projeto
Compose nomeado; o runner nunca recebe Docker socket.

O exemplo SampleEntity e as explicações originais estão preservados no primeiro
commit `493b956c152589d2cea4d6c0023f5133c787e019`. A versão atual foi adaptada ao
domínio bancário; não há rotas didáticas ativas ou testes antigos contabilizados
como garantias financeiras.
