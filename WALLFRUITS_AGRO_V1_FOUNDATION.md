# WallFruits Agro - Fundacao V1

Este documento marca a fundacao tecnica da V1 oficial dentro do codigo atual.

## O que ja foi implementado

- Perfil unico por usuario:
  - Tabela `profiles` com `profile_type` e `validation_status`.
  - Rotas para consultar/atualizar perfil e aprovar/rejeitar (admin).

- Assinaturas:
  - Tabela `subscriptions` com `plan_type` e status.
  - Conta nova recebe plano `basic` ativo.

- Publicacao de ofertas controlada:
  - Permissao centralizada em `app/core/domain_permissions.py`.
  - Apenas perfis aprovados de tipo `producer`, `broker` ou `company` podem publicar.

- Limite de visitante nas negociacoes:
  - Regra aplicada no fluxo de criacao de transacao.
  - Visitante nao premium limitado a 2 negociacoes por mes.

- Wallet com trilha de transacoes:
  - Tabelas `wallet` e `wallet_transactions`.
  - Bloqueio de atualizacao direta de saldo (somente via service/transacao registrada).

- Fundacao de dominios V1 criada:
  - Negotiations, negotiation messages, intermediation requests,
    reputation reviews, reports, raffles e raffle tickets.

- Intermediacao com fluxo admin:
  - Solicitacao por participante premium da negociacao.
  - Listagem historica por negociacao.
  - Listagem administrativa global com filtro de status.
  - Revisao administrativa (validada/rejeitada) com auditoria de quem analisou, quando e observacoes.

- Contrato de intermediacao e webhook:
  - Endpoint para anexar/atualizar contrato apos validacao da intermediacao.
  - Endpoint de upload binario de contrato no backend (arquivo real, sem depender apenas de URL externa).
  - Endpoint de download seguro do contrato com autorizacao por participante/admin.
  - Endpoint para leitura do contrato por participantes/admin.
  - Endpoint de historico de versoes de contrato para auditoria.
  - Webhook opcional para eventos de solicitacao, revisao e upsert de contrato.
  - Regra de fechamento: negociacao intermediada so conclui com intermediação validada e contrato anexado.

- Reputacao operacional:
  - Rotas para criar avaliacao, listar recebidas e obter resumo por perfil.
  - Regra de negocio: avaliacao somente apos negociacao com status `completed`.

- Denuncias e anti-fraude operacional:
  - Rotas para criar denuncia, listar minhas denuncias e painel admin com revisao.
  - Campos de auditoria de moderacao (quem revisou, quando e notas).
  - Auto-suspensao de perfil ao atingir limiar de denuncias graves pendentes.

- Arquitetura orientada a dominio:
  - Repository Pattern em `app/repositories`.
  - Service Layer em `app/services` para regras criticas.
  - Permissao centralizada por dependencias FastAPI.

## Ordem oficial de construcao (seguida)

1. Autenticacao e permissoes (iniciado)
2. Perfis (iniciado)
3. Ofertas (iniciado)
4. Negociacao (rotas e service ativos)
5. Assinaturas (base criada)
6. Wallet (base criada)
7. Reputacao e denuncias (operacional)
8. Gamificacao (pendente)
9. Sorteios (base criada)

## Proximos passos recomendados

1. Migrar completamente `offers` para `owner_profile_id` como obrigatorio.
2. Expor CRUD de `negotiations` separado de `transactions` legado.
3. Executar e expandir testes automatizados dos fluxos V1 no CI.
4. Evoluir webhook de intermediacao com assinatura, retry e idempotencia.
5. Evoluir upload de contrato com antivirus e regras de retencao/expurgo dos arquivos antigos.
6. Implementar gamificacao separada da wallet.
7. Consolidar regras de reputacao avancada (peso por valor negociado e contestacao).

## Comandos de validacao recomendados

1. `python -m unittest tests/test_v1_flows.py -v`
2. `python test_startup.py`
