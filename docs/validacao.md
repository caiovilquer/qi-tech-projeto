# Validação da API · 11/10/2026

## Ambiente e resultados

Validação local em macOS com Docker Engine 29.8.2. Aplicação, PostgreSQL 16.15,
MockServer 5.15.0 e pytest executados em containers Linux aarch64, com Python
3.11 e as versões diretas fixadas da base.

O código/testes do commit `d09385c` passou em **77 testes pytest**:

- 72 na suíte principal, em 10,10s.
- 2 de falhas de transporte, em 2,34s.
- 3 de erro inesperado, banco indisponível e sandbox desabilitado.

Calendário, replay, reinício, recuperação e sanitização de logs também foram
verificados. O roteiro completo terminou em 84,6s. A repetição em clone limpo e
volume novo passou nos mesmos 77 testes e ensaios, em 87,6s.

Para reproduzir em um projeto Compose isolado:

```bash
python3 tools/verify.py --project qit-verification --port 3300
```

O host controla reinícios e falhas; o runner não recebe Docker socket. Setup e
asserções de negócio passam pelas rotas HTTP. Nenhum teste importa código de
src, consulta SQL para provar regras de negócio ou substitui PostgreSQL por
SQLite/mock. Não há testes ignorados ou placeholders.

## Cenários executados

| Área | Evidência |
| --- | --- |
| Identidade | PF/PJ, CPF/CNPJ numérico/alfanumérico, zeros iniciais, documentos inválidos/duplicados e contexto autorizado |
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
- Instalação em clone limpo usa somente arquivos versionados e volume novo.
- APIs de teste usam a mesma imagem, variando apenas configuração de tarifas.
- Reinícios preservam volumes; reset não é utilizado como atualização de dados.
- Workflow GitHub Actions preparado para Ubuntu, com limite de 15 minutos.
  Os resultados registrados aqui são da execução local em containers Linux.

O bootstrap inicializa somente volume novo. Evoluções de schema com dados
existentes precisam de migração. Pix e bureau permanecem simulações de sandbox,
conforme o escopo da RFC.
