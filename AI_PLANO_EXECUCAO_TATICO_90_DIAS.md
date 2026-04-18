# Plano de Execucao Tatico - IA-Nativa (90 dias)

Data base: 2026-04-17
Objetivo: operar WallFruits em loops IA-nativos com governanca e impacto de negocio.

## 1) Norte de execucao

Modelo alvo
- Captar sinais -> Decidir com IA -> Executar por agentes -> Aprender em tempo real.

Restricao de seguranca
- Sem autonomia sem trilha de auditoria.
- Sem acao critica sem politica de risco.

## 2) Fase 1 (dias 1-30) - Fundacao de dados e governanca

### Entregas tecnicas
1. Taxonomia unica de eventos de negocio.
2. Envelope padrao de telemetria (dominio, source, request_id, idempotency).
3. Politicas de decisao por risco (baixo, medio, alto).
4. Fila L1 para revisao humana de decisoes IA.
5. Endpoints admin para listar e resolver fila de revisao.

### Entregas operacionais
1. Definir donos de cada agente.
2. Definir SLA por dominio (atendimento, comercio, pagamento).
3. Definir trilha minima de auditoria por acao.

### Criterio de pronto
- Fluxo de decisao IA com log, idempotencia e revisao humana ativa.

## 3) Fase 2 (dias 31-60) - Growth continuo e cockpit preditivo

### Entregas tecnicas
1. Ligar eventos de pagamento/checkout ao nucleo de decisao.
2. Ligar eventos de atendimento e mensagens ao nucleo de decisao.
3. Consolidar resumo de governanca (review_rate, autonomous_rate, backlog de revisao).
4. Expor painel admin com KPIs de governanca e fila de revisao.

### Entregas operacionais
1. Ritual semanal de ajuste de guardrails.
2. Revisao de experimentos de crescimento por segmento.
3. Acordo de aprovacao rapida para fila de risco medio.

### Criterio de pronto
- Decisao executiva e operacao diaria orientadas por painel IA.

## 4) Fase 3 (dias 61-90) - Escala de autonomia com controle

### Entregas tecnicas
1. Conectar sinais de produto e financeiro ao mesmo nucleo.
2. Ativar monitor de custo por decisao automatizada.
3. Implantar regras de subida/descida de autonomia por agente.
4. Automatizar ciclos de aprendizagem com relatorio semanal.

### Entregas operacionais
1. Revisao mensal de ROI por agente.
2. Reclassificacao de risco por dominio.
3. Plano de contingencia e rollback por fluxo critico.

### Criterio de pronto
- Operacao IA-nativa rodando em ciclo semanal de melhoria continua.

## 5) Backlog priorizado para hoje (execucao imediata)

1. Consolidar cobertura de testes para governanca e fila L1.
2. Fechar lacunas de persistencia/auditoria em metadados de revisao.
3. Adicionar visibilidade operacional no admin para governanca IA.
4. Publicar artefatos formais de arquitetura, agentes e plano 90 dias.

## 6) KPIs obrigatorios

Efetividade
- Tempo de resposta/resolucao.
- Conversao por segmento/canal.
- Retencao e expansao de receita.

Qualidade de decisao
- Taxa de acerto recomendacoes.
- Taxa de rollback.
- Percentual de decisoes com intervencao humana.

Economia
- Margem por jornada.
- Custo por decisao automatizada.

Risco
- Taxa de revisao humana.
- Incidentes de compliance por periodo.

## 7) Ritos operacionais

Diario (30 min)
1. Alertas criticos e itens vencidos na fila L1.
2. Anomalias de conversao, margem e suporte.

Semanal (90 min)
1. Ajuste de guardrails e thresholds.
2. Priorizacao de experimentos e alocacao de capacidade.

Mensal (120 min)
1. ROI por agente.
2. Evolucao de autonomia por dominio.
3. Revisao de riscos e controles.

## 8) Definicao de sucesso ao final de 90 dias

1. Decisoes IA com rastreabilidade completa em dominios criticos.
2. Fila L1 com SLA controlado e auditoria consolidada.
3. Operacao orientada por KPIs em tempo real.
4. Evolucao de autonomia baseada em risco e resultado, nao em opiniao.
