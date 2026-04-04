# ADS Setup Guide (WallFruits)

Este guia ativa monetizacao de anuncios em todas as abas com foco em UX e conversao.

## 1) Configuracao rapida (recomendada)

Abra o site em producao, pressione `F12` e rode no Console:

```javascript
wfApplyAdsStarterConfig('hybrid')
```

Esse perfil faz:
- provider = `adsense`
- fallback patrocinado ativo
- slots top/bottom ja preenchidos com placeholders

## 2) Ajustar IDs reais do AdSense

Troque pelos valores reais da sua conta:

```javascript
wfSetAdsConfig({
  provider: 'adsense',
  enabled: true,
  adsense_client: 'ca-pub-SEU_CLIENT_ID',
  slots: {
    top: 'SEU_SLOT_TOP',
    bottom: 'SEU_SLOT_BOTTOM'
  }
})
```

## 3) Usar rede terceira por script (opcional)

```javascript
wfSetAdsConfig({
  provider: 'custom-script',
  enabled: true,
  script_url: 'https://seu-servidor-de-ads.exemplo/sdk.js'
})
```

## 4) Fallback patrocinado local (sempre recomendado)

```javascript
wfSetAdsConfig({
  sponsored: [
    {
      title: 'Patrocinado: sua marca no agro',
      text: 'Campanhas para produtores, compradores e prestadores de servico.',
      href: 'https://seu-dominio.com/campanha-1',
      cta: 'Conhecer'
    },
    {
      title: 'Anuncie na WallFruits',
      text: 'Gere leads qualificados em publico com intencao comercial.',
      href: 'https://seu-dominio.com/campanha-2',
      cta: 'Anunciar'
    }
  ]
})
```

## 5) Medir resultado

Ver metricas locais (impressoes/cliques por contexto, slot e provider):

```javascript
wfGetAdMetrics()
```

Ver painel completo (metricas + estado de entrega + sessao + viewability):

```javascript
wfGetAdInsights()
```

Resetar metricas locais:

```javascript
wfResetAdMetrics()
```

## 6) Ver configuracao atual

```javascript
wfGetAdsConfig()
```

## 7) Perfis prontos

```javascript
wfGetRecommendedAdsConfig('fallback')
wfGetRecommendedAdsConfig('hybrid')
wfGetRecommendedAdsConfig('custom-script')
```

## 8) A/B test de posicionamento (ativo por padrao)

O motor agora distribui automaticamente usuarios entre variantes por contexto (bucket estavel por usuario).

Para desligar o experimento:

```javascript
wfSetAdsConfig({
  experiment: {
    enabled: false
  }
})
```

Para reduzir rollout da variante B (exemplo 30%):

```javascript
wfSetAdsConfig({
  experiment: {
    enabled: true,
    rollout: 0.3,
    variants: ['a', 'b']
  }
})
```

## 9) Controle de frequencia e fadiga

Use limites para evitar excesso de anuncios por usuario e por slot:

```javascript
wfSetAdsConfig({
  frequency: {
    session_cap_per_slot: 5,
    daily_cap_per_slot: 22,
    fatigue_no_click_threshold: 10,
    fatigue_hard_threshold: 18
  }
})
```

Regras atuais:
- Ao atingir `fatigue_no_click_threshold`, o slot de baixo e reduzido.
- Ao atingir `fatigue_hard_threshold`, a entrega e pausada ate novo ciclo.

## 10) Viewability score por slot

Cada ad hidratado ganha score local de viewability (0-100) com base em:
- Percentual maximo visivel
- Tempo visivel acumulado

Consultar somente viewability:

```javascript
wfGetAdViewabilityReport()
```

## Boas praticas para ganhar mais

- Use criativos diferentes por contexto (home, comunidade, ofertas, loja).
- Evite anuncios em telas de foco intenso (mensagens) para nao reduzir retencao.
- Revise metricas semanalmente e troque textos de CTA dos patrocinados.
- Mantenha fallback patrocinado ativo para nunca ficar sem monetizacao.
