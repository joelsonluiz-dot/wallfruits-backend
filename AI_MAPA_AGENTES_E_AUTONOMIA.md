# Mapa de Agentes e Limites de Autonomia - WallFruits

Data: 2026-04-17
Escopo: operacao IA-nativa com governanca por risco.

## 1) Objetivo

Definir quem decide, quem executa e quando escalar para humano.
Este documento e operacional: pode ser usado por produto, engenharia, operacao e risco.

## 2) Niveis de autonomia

L0 Observador
- IA so monitora sinais e sugere acao.

L1 Recomendador
- IA prepara recomendacao com justificativa.
- Humano aprova antes de executar.

L2 Executor com guardrails
- IA executa automaticamente dentro de limites aprovados.
- Toda acao tem trilha de auditoria.

L3 Executor ampliado
- IA executa ponta a ponta em fluxos estaveis.
- Revisao humana por amostragem e auditoria continua.

## 3) Agentes centrais

### 3.1 Orquestrador central
Missao
- Receber sinais de negocio e distribuir para agente especialista.

Entradas
- Eventos de atendimento, comercio, pagamento, risco, operacao e produto.

Saidas
- Plano de acao priorizado.
- Definicao do nivel de autonomia por risco.

Autonomia alvo
- L2.

Limite critico
- Nao aprova excecao de alto risco sem humano.

### 3.2 Agente de atendimento
Missao
- Triagem, resposta, resolucao e handoff para humano.

Entradas
- Mensagens, contexto de conta, historico de pedidos e suporte.

Saidas
- Respostas, tickets, alertas de crise, handoff comercial.

Autonomia alvo
- L2 para casos repetitivos.

Limite critico
- Fraude, juridico, conflito severo e bloqueio de conta sempre em L1.

### 3.3 Agente de crescimento
Missao
- Segmentar, personalizar oferta, testar mensagem e otimizar canal.

Entradas
- Eventos de funil, checkout, assinatura e comportamento de uso.

Saidas
- Campanhas adaptativas, hipoteses e recomendacao de verba.

Autonomia alvo
- L2.

Limite critico
- Alteracao estrutural de preco ou contrato exige aprovacao humana.

### 3.4 Agente de produto
Missao
- Transformar sinais de friccao em backlog priorizado por impacto.

Entradas
- Feedback, analytics de jornada, perda de venda, erros e suporte.

Saidas
- Hipoteses priorizadas, experimentos e criterio de sucesso.

Autonomia alvo
- L1.

Limite critico
- Sem rollout amplo sem aprovacao de produto/engenharia.

### 3.5 Agente de comercio autonomo
Missao
- Recomendar e executar acoes de negociacao e leilao dentro de guardrails.

Entradas
- Snapshot de mercado, oferta, perfil, risco e margem.

Saidas
- Evento de negociacao, leilao, recomendacao de rollback, trilha de decisao.

Autonomia alvo
- L2.

Limite critico
- Saiu de margem, risco alto ou guardrail quebrado: cria fila L1.

### 3.6 Agente de risco e compliance
Missao
- Avaliar risco operacional, financeiro e reputacional.

Entradas
- Disputas, cancelamentos, denuncias e anomalias.

Saidas
- Score de risco, nivel de autonomia permitido, bloqueios preventivos.

Autonomia alvo
- L1 no inicio, evoluindo para L2.

Limite critico
- Bloqueio definitivo exige decisao humana.

### 3.7 Agente de gestao executiva
Missao
- Converter sinais em decisoes executivas com impacto e prazo.

Entradas
- KPIs, alertas preditivos e desvios de meta.

Saidas
- Plano executivo, donos de acao e follow-up.

Autonomia alvo
- L1.

Limite critico
- Sem mudanca de meta corporativa sem lideranca humana.

## 4) Matriz de autonomia por risco

Baixo risco
- IA executa automaticamente.
- Exige log de decisao e idempotencia.

Medio risco
- IA recomenda e prepara contexto.
- Humano aprova em fila de revisao.

Alto risco
- IA apenas recomenda.
- Humano decide e assina trilha de auditoria.

## 5) Politicas obrigatorias de governanca

1. Toda decisao autonoma precisa de event_id e request_id.
2. Toda decisao com risco medio/alto precisa de justificativa de politica.
3. Todo item em revisao humana precisa de status, decisao e auditor.
4. Toda acao reversivel precisa de caminho de rollback conhecido.

## 6) KPIs por agente

Atendimento
- Tempo de primeira resposta.
- Resolucao sem humano.

Crescimento
- CTR por segmento.
- Conversao para checkout.

Produto
- Tempo descoberta -> experimento.
- Impacto por experimento.

Comercio autonomo
- Taxa de acao aprovada automaticamente.
- Taxa de rollback e conflito.

Risco e compliance
- Taxa de revisao humana.
- Incidentes por politica.

Gestao
- Tempo para corrigir desvio.
- Taxa de execucao de plano.

## 7) Regra de evolucao de autonomia

Para subir de nivel (ex.: L1 -> L2), o agente precisa atender:
1. Taxa de erro abaixo do limite da politica por 4 semanas.
2. Auditoria sem incidente critico no periodo.
3. Custos por decisao dentro do teto aprovado.
4. Testes de regressao e fallback validados.
