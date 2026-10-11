# Implementação bancária

O serviço implementa a [RFC v8](RFC-v8.md) em um monólito Python/FastAPI,
com PostgreSQL 16 e cinco entidades: customer, account, operation, account_entry
e account_status_event. Os contratos JSON são estritos; valores monetários usam
centavos inteiros de BRL, com teto de 2^53−1.

## Organização do código

| Camada | Responsabilidade |
| --- | --- |
| resources/schemas | Adaptar HTTP e validar corpo, UUIDs, cabeçalhos e filtros |
| controllers | Autorizar recursos, aplicar regras e coordenar transações |
| repositories/models | Consultar, reservar chaves, obter locks e persistir dados |
| dtos | Selecionar os campos públicos e limitar a visibilidade por conta |
| connectors | Consultar o bureau simulado, com timeout de conexão/leitura |
| middlewares | Autenticar, correlacionar requisições, registrar logs e encerrar sessões |

Repositories não fazem commit. Cada controller usa o contexto de sessão da
requisição. O middleware fecha a sessão em todos os caminhos; raiz e liveness
não precisam abrir conexão com o banco. O [guia de organização](como-o-projeto-e-organizado.md)
detalha esse ciclo e os arquivos envolvidos.

## Cadastro, abertura e estados

Cadastro PF/PJ normaliza e valida CPF/CNPJ numérico ou alfanumérico, preservando
zeros e letras. A criação usa chave UUID durável por integrador/comando, com
INSERT ON CONFLICT e SELECT separado para recuperar o resultado concorrente.
Documento duplicado e chave com intenção diferente têm recusas distintas.

A abertura persiste PENDING, saldo zero e evento inicial antes de consultar o
bureau. A sessão é fechada durante o HTTP externo. Uma nova transação obtém
FOR NO KEY UPDATE da conta e aplica a conclusão somente se ela continuar
PENDING. REGULAR aprova; IRREGULAR/NOT_FOUND recusa; dívida é informativa.
Falha técnica conserva pendência, retomada pelo mesmo POST/chave. GET só consulta.

Bloqueio/desbloqueio usa expected_version, motivo e histórico de eventos.
Reenvio da última transição não duplica histórico; uma versão antiga não
reaplica bloqueio depois de desbloqueio. BLOCKED recebe créditos, mas não
executa novos débitos. Replay monetário confirmado continua recuperável.

## Escrita financeira

Aporte e transferência seguem uma única fronteira de commit:

1. Validar entrada, autenticar e autorizar a conta da rota; resolver o destino.
2. Reservar imediatamente a chave por INSERT ON CONFLICT.
3. Em conflito, fazer SELECT separado em READ COMMITTED e comparar a intenção.
   Replay recupera operação e tarifa originais, sem revalidar saldo/estado/quota.
4. Para Pix novo, coordenar o cliente antes das contas. Contas são bloqueadas
   por ID crescente com FOR NO KEY UPDATE.
5. Reler saldos/estados frescos e obter um único instante depois dos locks.
6. Validar estado, principal+tarifa, teto do destino e quota compartilhada.
7. Aplicar UPDATE relativo/RETURNING e inserir entries: principal antes da
   tarifa na origem, somente principal no destino. Tarifa zero não cria entry.
8. Fazer flush, preparar o DTO e confirmar um único COMMIT antes da resposta.

Recusa pré-COMMIT desfaz a reserva e os efeitos. Perda da confirmação do COMMIT
conserva resultado desconhecido e exige recuperação pela mesma chave. A chave
não expira em 24 horas. Saldo atual e balance_after_cents são reconciliáveis
pelos lançamentos confirmados.

## Pix, consultas e privacidade

Pix é uma modalidade local entre contas existentes. A quota soma somente o
principal enviado em operações confirmadas do cliente, entre todas as suas
contas. As janelas usam America/Sao_Paulo, e o período noturno atravessa a
meia-noite sem reiniciar o consumo.

Extrato usa cursor por entry_key, ordem decrescente e filtros temporais
[from,to). O marcador precisa existir na conta e no intervalo autorizados.
Detalhe é completo em ordem crescente e expõe somente as entries daquela
conta; o destinatário vê seu crédito, sem saldo, tarifa global ou dados da
contraparte.

## Configuração e validação

Compose constrói a imagem, mantém o banco em volume persistente e usa
credenciais distintas para negócio e readiness. api-fee0 compartilha imagem e
banco, com tarifas zero. O perfil fault adiciona uma instância e um proxy
somente para ensaios de transporte. O relógio fixo só é permitido no ambiente
test, sem endpoint/cabeçalho público para manipulá-lo.

A suíte usa pytest e HTTP real com PostgreSQL, prepara cenários pelas rotas e
substitui somente o bureau por MockServer. O roteiro `tools/verify.py` executa
72 testes principais e 5 de falhas operacionais/transporte, além dos ensaios
de calendário, reinício e recuperação. A [matriz de erros](erros-testes.md) cobre
os 27 códigos públicos; [validacao.md](validacao.md) registra os resultados.

A origem da API permanece no commit
`493b956c152589d2cea4d6c0023f5133c787e019`, com os arquivos originais da Aula 1.
O núcleo foi adaptado ao domínio bancário; os contratos didáticos de
SampleEntity não integram as rotas atuais.
