# Implementação da RFC v8

Base original: `493b956c152589d2cea4d6c0023f5133c787e019`. 67 arquivos
comparados byte a byte ao ZIP antes do commit; árvore Git conferida também
com a normalização LF prevista em `.gitattributes`. Nenhuma edição prévia.
Git inicializado somente nesta API. Fontes externas são somente leitura.

## Etapas

1. Schema de cinco entidades, configuração, Compose, sondas e instalação limpa.
2. PF/PJ, identidade delegada e criação idempotente.
3. Abertura persistida, bureau, retomada e estados versionados.
4. Aporte e transferência, tarifa, entries, reserva e commit único.
5. Pix simulado, quota por cliente e concorrência.
6. Consultas, cursor, filtros e detalhe por conta.
7. Matriz integrada, falhas reais de transporte, reinício, relógio de teste,
   reconciliação e documentação reproduzível.

Cada etapa termina com testes HTTP/PostgreSQL e commit próprio. Repositories
não comitam. Controllers controlam transações; a sessão da base é encerrada
antes do bureau. Entradas JSON Schema estritas; consultas usam projeções
frescas; NO KEY UPDATE mantém compatibilidade com KEY SHARE das FKs.

A especificação copiada em [RFC-v8.md](RFC-v8.md) e seus diagramas preservam
os caminhos relativos. G-09/G-10/G-11 seguem como confirmações externas.

## Evidências e decisões locais

- Docker disponível: engine 29.8.2. Testes rodam em containers Linux isolados.
- Base preservada no primeiro commit, inclusive dois avisos preexistentes de
  linha vazia no fim do Dockerfile e Compose.
- Estado das etapas e resultados serão registrados conforme execução.

### Etapa 1 concluída

Build Linux com todas as versões diretas originais instalado. Schema de cinco
entidades criado em volume novo; readiness verifica suas colunas sem escrita.
`docker compose -p qit-implementation --profile test run --rm runner`: 1 teste
HTTP aprovado, incluindo sondas e separação das credenciais. Removidos os
módulos/testes didáticos de SampleEntity após preservação no commit inicial.

### Etapa 2 concluída

Cadastro PF/PJ com normalização e validação CPF/CNPJ, incluindo vetor oficial
alfanumérico `12.ABC.345/01DE-35` do manual da Receita Federal. JSON Schema
recusa campos extras; validador de inteiros foi especializado para recusar
floats integrais. Contexto delegado e DTO sem IDs/chaves internas. INSERT
ON CONFLICT e SELECT separado arbitram criação entre processos.
Suíte Linux HTTP: 10 aprovados, sem SQL de teste/importação de src.

### Etapa 3 concluída

Abertura cria PENDING/evento inicial antes do connector; fecha Session e libera
a conexão antes de HTTP. Nova sessão relê a conta com NO KEY UPDATE. Conclusão
única conserva evidência mínima; GET não conclui. Replay consulta o evento de
abertura, mesmo após bloqueio. Comando de estado com versão, no-op e proteção
contra reenvio antigo. Listagem e autorização por conta implantadas.
Suíte Linux HTTP: 21 aprovados em 7,13s; bureau REGULAR/IRREGULAR/NOT_FOUND,
dívida informativa, erro/timeout/malformado, retomada, resposta tardia,
concorrência de abertura, versões e privacidade.

### Etapa 4 concluída

Aportes e INTERNAL usam reserva imediata, SELECT separado para replay,
NO KEY UPDATE por ID crescente, projeções frescas e UPDATE relativo/RETURNING.
Principal precede tarifa; zero fee não cria entry. Saldo, operação e entries
comitam juntos. Consultas financeiras foram antecipadas para verificar os
efeitos e reconciliar cada lançamento já nesta fatia; sua matriz será ampliada
na etapa 6. Replay preserva tarifa mesmo na fee0 e depois de bloqueio.
Suíte Linux HTTP: 38 aprovados em 7,44s. Gasto duplo, A↔B e mesma chave entre
instâncias avaliam a primeira tentativa, sem retries. Recusas não alteram
histórico/saldos; chave recusada é reutilizável após aporte. Teto 2^53−1 e
inteiros estritos validados. Saldo e balance_after reconstruídos pela API.

### Etapa 5 concluída

Pix coordena primeiro o cliente com NO KEY UPDATE, depois contas por ID.
Quota soma somente TRANSFER_DEBIT de PIX_SIMULATED confirmado na janela
America/Sao_Paulo, após locks e com o mesmo instante usado nas entries.
Sem contador/cache; principal, tarifa e recebimentos tratados separadamente.
Suíte Linux HTTP: 42 aprovados. Quota compartilhada entre contas concorrentes,
Pix entre contas próprias, limite exato, tarifas PF/PJ e replay preservados.
APIs iniciadas em APP_ENV=test, TEST_CLOCK=2026-10-11T12:00:00Z; runner --no-deps
para preservar essa configuração durante os testes (Compose run sem isso pode
recriar dependências com ambiente diferente).

### Etapa 6 concluída

DTOs filtram detalhe por conta e extrato por lançamento. Cursor resolve apenas
na conta/intervalo autorizados; entradas novas não deslocam páginas antigas.
Datas RFC3339 com offset válido, [from,to), parâmetros desconhecidos/repetidos
recusados. Destinatário vê somente seu crédito; sem IDs, tarifa global ou
chave de idempotência. Detalhe ASC, extrato DESC; página vazia/final explícita.
Suíte Linux HTTP: 57 aprovados; inclui corrida bloqueio/débito e comandos de
estado distintos concorrentes, com reconciliação e primeira tentativa.

### Etapa 7: transporte real concluído

Perfil fault acrescenta proxy PostgreSQL de protocolo (somente teste), sem
alterar a imagem da API. Interrompe INSERT antes de encaminhar: 503/QIT001014,
sem saldo/entries; mesma chave depois confirma uma vez. Descarta CommandComplete
de COMMIT depois de o PostgreSQL confirmar: 503/QIT001027, saldo/entries já
persistidos; replay na fee0 recupera a operação sem débito duplicado.
`runner python fault_transport.py` aprovado em containers Linux. Não há
failpoints na API, mock de banco ou socket Docker montado no runner.
api/api-fee0 agora apontam explicitamente para a mesma tag/imagem construída;
o terceiro processo existe somente para o ensaio de transporte.
