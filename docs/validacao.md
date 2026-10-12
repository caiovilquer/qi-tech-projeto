# Validação da API · 11/10/2026

## Ambiente e resultados

Revisão local em WSL2/Linux x86_64, com Docker Engine 29.8.1 e Compose 5.5.1.
Aplicação, PostgreSQL 16.15, MockServer 5.15.0 e pytest executados em containers
Linux, com Python 3.11.17 e as dependências diretas fixadas da base.

Base versionada: `5ff7373`, acrescida das correções locais desta revisão.
Resultado final: **90 testes pytest aprovados**, sem falhas ou testes ignorados:

| Etapa | Resultado | Duração |
| --- | --- | --- |
| Suíte principal | 85 aprovados | 16,32s |
| Falhas reais de transporte PostgreSQL | 2 aprovados | 3,95s |
| Erro inesperado com resposta segura | 1 aprovado | 0,06s |
| Banco indisponível | 1 aprovado | 0,10s |
| Sandbox desabilitado | 1 aprovado | 1,16s |

Calendário, replay após 24h, mudança de tarifa, reinícios, recuperação e
sanitização dos logs também passaram. O roteiro completo registrou **154,5s**
e terminou com código de saída zero, incluindo a restauração final das APIs.

Para reproduzir em um projeto Compose isolado:

```bash
python3 tools/verify.py --project qit-audit-20261011 --port 3400
```

O projeto Compose da auditoria possui volume próprio, criado no primeiro ensaio
e preservado durante as repetições. Os projetos preexistentes `qit-banking` e
`qit-verification` não foram usados para provocar falhas ou reinícios.
Ao final, os containers da auditoria foram encerrados com `down`, sem remover
o volume. As imagens dos ambientes preexistentes não foram reconstruídas.

A execução final também verificou o isolamento da configuração: o shell
forneceu tarifas 888/777/333/444 e quotas diurna/noturna de 1 centavo; o roteiro
aplicou os valores de teste da RFC e todos os cenários passaram.

O host controla reinícios e falhas; o runner não recebe Docker socket. Setup e
asserções de negócio passam pelas rotas HTTP. Nenhum teste importa código de
src, consulta SQL para provar regras de negócio ou substitui PostgreSQL por
SQLite/mock. Não há testes ignorados ou placeholders.

## Problemas encontrados e corrigidos

- A execução inicial teve 71 aprovações e uma falha em
  `test_late_external_response_cannot_replace_decision[200]`, em 105,72s.
  O teste supunha uma ordem de execução a partir de pausas de 300ms/1s e
  passou quando repetido isoladamente. Agora o mock encaminha a primeira
  consulta a uma resposta HTTP controlada pelo runner, liberada apenas após
  a conclusão concorrente. O teste verifica essa ordem sem retries.
- Nome, email e motivo com NUL ou surrogates Unicode isolados provocavam
  500/QIT000500. Agora são recusados com 400/QIT000001, sem consumir a chave
  de cadastro nem alterar estado/versão. Acentos e emojis válidos são aceitos.
- Referência inválida do bureau provocava 500 sem a chave da conta pendente.
  Agora retorna 503/QIT001031 com `details.account_key`, mantém PENDING e
  permite retomar a mesma conta pelo mesmo POST/chave.
- O runner herdava parte das tarifas/quotas do ambiente local. O roteiro
  agora fixa todas elas para a suíte e encerra as ferramentas de falha no
  `finally`, inclusive se uma etapa não passar.

Foram acrescentados 13 casos HTTP de regressão. Antes do roteiro completo,
os 29 testes de abertura e erros passaram em uma execução dirigida de 9,98s.

## Cenários executados

| Área | Evidência |
| --- | --- |
| Identidade | PF/PJ, CPF/CNPJ numérico/alfanumérico, zeros iniciais, documentos inválidos/duplicados e contexto autorizado |
| Textos | NUL e Unicode inválido recusados; chave, estado e versão preservados; acentos e emojis válidos |
| Criação | Mesmo pedido/chave e intenções distintas entre processos; documento duplicado com chaves diferentes |
| Bureau | Regular, irregular, não encontrado, dívida, corpo inválido, falha HTTP e timeout; retomada e conclusão única |
| Estados | Bloqueio/desbloqueio versionado, no-op, reenvio antigo e corridas com débito ou outro comando administrativo |
| Dinheiro | Principal+tarifa, teto, inteiros estritos, quatro tarifas PF/PJ/modalidade, tarifa zero sem delta zero e recusa sem efeitos |
| Concorrência | Gasto duplo, A↔B, mesma chave, intenção distinta, reserva abortada e quota compartilhada entre contas |
| Reconciliação | Deltas e balance_after_cents reconstroem saldo; saldos+tarifas correspondem aos aportes |
| Consultas | Detalhe ASC, extrato DESC, destinatário isolado, cursor inválido/alheio, filtros, páginas finais/vazias e novas entradas |
| Calendário | Bordas de 06h e 20h, meia-noite sem reset da quota noturna, limite exato e replay após mais de 24h |
| Persistência | Reinícios de APIs/banco conservam saldos, histórico, chaves e abertura pendente; retomada usa a mesma conta |
| Configuração | Tarifa alterada afeta operação nova e preserva replay; sandbox desabilitado; relógio de teste recusado no modo normal |
| Infraestrutura | Raiz, liveness/readiness, credenciais separadas, 403/404/405, acentos e correlação de falhas 500 |
| Logs | Ausência de credenciais/documentos e presença das classificações confirmado, replay e desconhecido |

A [matriz de erros](erros-testes.md) relaciona os 27 códigos públicos aos testes.
As primeiras tentativas concorrentes são avaliadas sem retries; recuperação é
verificada em cenários separados.

## Falhas reais

O perfil fault usa um proxy de protocolo PostgreSQL, com a mesma imagem da API:

1. INSERT de operation interrompido antes de ser encaminhado: 503/QIT001014,
   sem saldo/entries; reenvio confirma uma única operação.
2. CommandComplete de COMMIT descartado depois de o banco confirmar:
   503/QIT001027 com dinheiro/histórico persistidos; mesma chave na fee0 recupera
   o UUID sem novo débito.
3. Arquivo de schema temporariamente indisponível na API de teste: 500 seguro,
   preservando X-Request-ID e sem expor documento, credencial ou caminho interno.

Banco e bureau foram também parados pelo host e recuperados. O banco parado
manteve liveness 204 e produziu readiness/escrita 503; o bureau indisponível
conservou PENDING, retomado pelo mesmo POST/chave. Todos os testes de erro
inesperado restauram a configuração do container ao final.

## Reprodutibilidade

- Schema gerado pelos models corresponde ao database.sql de bootstrap.
- Bootstrap executado em volume isolado novo; repetições conservaram os dados.
- API principal e api-fee0 usam a mesma imagem/banco, variando as tarifas;
  api-fault usa essa imagem com acesso ao banco pelo proxy de teste.
- Reinícios preservam volumes; reset não é utilizado como atualização de dados.
- `docker compose --profile test --profile fault config -q` e `pip check`
  passaram; sintaxe Python, JSONs, SVGs e links locais da documentação conferidos.
- O PDF da RFC foi aberto e teve suas 17 páginas e 18 seções verificadas.
- Workflow GitHub Actions preparado para Ubuntu, com limite de 15 minutos.
  Esta revisão não executou o workflow remoto nem mediu cobertura de linhas.

O bootstrap inicializa somente volume novo. Evoluções de schema com dados
existentes precisam de migração. Pix e bureau permanecem simulações de sandbox,
conforme o escopo da RFC.

## Registro anterior

O registro preservado da validação em macOS, Docker Engine 29.8.2 e Linux
aarch64 refere-se ao código/testes de `d09385c`: 77 testes aprovados
(72 principais, 2 de transporte e 3 operacionais), com roteiro de 84,6s e
repetição em clone limpo/volume novo de 87,6s. Esses números são históricos;
os resultados atuais em WSL2 estão detalhados acima.
