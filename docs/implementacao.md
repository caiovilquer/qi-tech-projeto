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
