# Evidências de validação · 11/10/2026

## Ampliação de regressões e erros públicos

Código/testes do commit `d09385c`: **77 testes pytest aprovados**, sendo 72 na
suíte principal e 5 nas etapas de transporte/erro operacional. Os 27 códigos
públicos possuem cenários explícitos na [matriz de erros](erros-testes.md).
Registros anteriores de 64 testes abaixo descrevem a validação inicial.

```bash
python3 tools/verify.py --project qit-error-regression --port 3304
```

Resultado: 72 pytest em 10,10s; 2 de transporte em 2,34s; erro inesperado,
banco parado e sandbox desabilitado em execuções pytest específicas. Calendário,
replay, reinícios, indisponibilidade e logs também aprovados. Total 84,6s.
Dois defeitos foram observados em testes antes das correções: correlação ausente
na resposta 500 e UTF-8 inválido classificado como erro interno.

Clone limpo do commit d09385c, volume novo qit-errors-clean_bank-data:
72 pytest em 10,10s e 5 pytest operacionais/de transporte aprovados; todos os
ensaios também aprovados. Roteiro completo 87,6s. Logs locais em
`.git/error-clean-verification.log`.

## Validação inicial no ambiente local

Docker Engine 29.8.2 em macOS; aplicação, PostgreSQL 16.15, MockServer 5.15.0 e
pytest executados em containers Linux aarch64. Python 3.11, dependências diretas
originais fixadas. Nenhum SQLite/mock de banco, importação de src nos testes,
SQL para provar regras de negócio, teste ignorado ou placeholder.

Comando completo:

```bash
python3 tools/verify.py --project qit-implementation --port 3000
```

Resultado: **64 testes pytest aprovados em 9,45s**, mais os ensaios HTTP do host
abaixo. Roteiro completo concluído em **81,6s**. O host controla reinícios,
sem Docker socket no runner. Todas as primeiras tentativas concorrentes são
avaliadas diretamente; não há retry automático na função de requisição.

| Área | Evidência executada |
| --- | --- |
| Identidade | PF/PJ, CPF/CNPJ numérico/alfanumérico, zeros iniciais, vetor da Receita, documentos inválidos, contexto/tokens e isolamento de contas |
| Criação | Mesma chave/pedido e pedidos distintos entre processos; documento duplicado com chaves distintas; recuperação de identificador |
| Bureau | Regular, irregular, não encontrado, dívida, HTTP inválido, corpo malformado, timeout; pendência retomável; resposta tardia/erro tardio não substituem conclusão |
| Estado | Bloqueio/desbloqueio versionado, no-op, reenvio antigo, corrida de motivos distintos, bloqueio concorrente com débito; créditos em BLOCKED |
| Dinheiro | Principal+tarifa, teto, inteiros sem coerção, zero fee sem delta zero, quatro tarifas PF/PJ/modalidade, recusa sem efeitos e reaproveitamento de chave recusada |
| Concorrência | Gasto duplo, A↔B, mesma chave, conteúdo distinto, reserva abortada seguida de insert concorrente, quota entre contas do cliente |
| Histórico | Soma de deltas e cada balance_after reconstroem saldo; saldos+fees=aportes; detalhe ASC e extrato DESC |
| Consultas | Recebedor vê só crédito; outras contas não veem operação; cursor próprio/alheio/inválido, novas entradas entre páginas, filtros [from,to), fim e vazio |
| Calendário | 19:59:59, 20:00:00, meia-noite, 05:59:59 e 06:00:00 em America/Sao_Paulo; quota noturna compartilhada sem reset à meia-noite |
| Persistência | Reinícios de APIs e PostgreSQL conservam saldos, histórico, chaves e abertura pendente; retomada aprova a mesma conta |
| Retenção/tarifa | Replay após mais de 24h e alteração de 200 para 999 conserva operação/fee original; operação nova usa tarifa nova |
| Indisponibilidade | Banco parado: liveness 204, readiness/escrita 503; banco reiniciado recupera operação; bureau parado mantém PENDING e retoma na recuperação |
| Sandbox/relógio | Aporte desabilitado não escreve; TEST_CLOCK recusado fora de APP_ENV=test; relógio só por startup, sem endpoint/cabeçalho |
| Logs | Credenciais/documento fictício ausentes; confirmado/replay/desconhecido presentes; sem parâmetros SQL sensíveis |

## Falhas reais de transporte

`tests/fault_transport.py`, via proxy de protocolo PostgreSQL em perfil fault:

1. INSERT de operation interrompido antes de encaminhar ao banco:
   503/QIT001014, sem dinheiro/histórico; mesma chave depois confirma uma vez.
2. PostgreSQL devolve CommandComplete de COMMIT, proxy descarta confirmação:
   503/QIT001027, dinheiro/histórico já persistidos; replay pela fee0 recupera
   o UUID sem novo efeito. Portanto 503 não foi presumido como rollback.

Nenhum failpoint na API, mock de repository ou SQL de assertiva financeira.
api/api-fee0 usam o mesmo digest de imagem; configuração de tarifas é a diferença.
O terceiro processo/proxy é exclusivo do ensaio e fica parado depois dele.

## Reprodutibilidade e limites

- Schema gerado pela imagem testada corresponde ao database.sql.
- 705 arquivos externos protegidos (site, fontes, análises, aulas, referências
  e publicação) comparados por SHA-256: nenhum mudou.
- O commit inicial contém exatamente os 67 arquivos do ZIP, respeitando apenas
  a normalização LF já prevista na base; não foi reescrito.
- Clone local limpo do commit `a4ce6e9`, em `.git/clean-checkout`, e volume novo
  `qit-clean-validation_bank-data`: **64 pytest aprovados em 9,65s** e todos os
  ensaios completos, em **79,7s**. Executado com
  `python3 .git/clean-checkout/tools/verify.py --project qit-clean-validation --port 3301`.
  API, PostgreSQL, MockServer e runner em containers Linux; arquivos somente do Git.
  Logs locais em `.git/clean-verification.log`.
- Workflow Ubuntu/GitHub Actions preparado, com limite de 15 minutos; não foi
  executado remotamente. Os resultados acima são locais, em containers Linux.
- Não houve deploy, push ou criação de repositório remoto. Pix e bureau são
  simulações de sandbox, conforme a RFC.

O harness restaura as duas APIs ao instante de teste padrão e sandbox habilitado,
preservando o volume. Logs detalhados locais ficaram em `.git/verification-final.log`
(fora da árvore versionada); esta síntese e o roteiro permitem reproduzir a prova.

O Compose padrão `qit-banking` foi iniciado em sandbox com relógio normal e
volume próprio novo, em localhost:3000; raiz HTTP 200 e readiness autenticada
HTTP 204. Ambientes temporários qit-implementation e qit-clean-validation foram
parados sem apagar seus volumes de dados fictícios. Git principal sem remote,
sem alterações pendentes, e hash inicial/RFC/fontes protegidas auditados.
