# Arquitetura do Sistema

## Visão Geral

```
┌─────────────────────────────────────────────────────────────────┐
│                         FONTES DE DADOS                          │
├─────────────────┬───────────────────────────────────────────────┤
│  Meta Ads API   │  Rezdy API + Webhooks                         │
│  (near realtime)│  (quasi realtime)                             │
└────────┬────────┴──────────┬──────────────────────────────────┘
         │                   │
         ▼                   ▼
┌────────────────┐   ┌───────────────────────────────────────────┐
│ meta_ads_worker│   │ POST /webhooks/rezdy                       │
│ (APScheduler)  │   │   ├─ Valida assinatura HMAC               │
│ ├─ 30min: 3d   │   │   ├─ payload_hash idempotência            │
│ └─ 03h: 30d    │   │   ├─ INSERT raw_events (ignore duplicate) │
└───────┬────────┘   │   └─ Background: transform_worker         │
        │             └──────────────────────────────────────────┘
        │                              │
        ▼                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        POSTGRESQL / SUPABASE                     │
│                                                                   │
│  raw_events (append-only, jsonb bruto)                           │
│  ├── fact_meta_ad_performance_daily (upsert diário)              │
│  ├── fact_rezdy_bookings (upsert por order_number)               │
│  ├── fact_funnel_touchpoints (atribuição)                        │
│  ├── fact_sync_health (monitoramento)                            │
│  └── dim_* (dimensões: campanhas, produtos, clientes)            │
│                                                                   │
│  Views analíticas:                                               │
│  ├── v_kpi_executive                                             │
│  ├── v_meta_ads_daily                                            │
│  ├── v_rezdy_bookings_daily                                      │
│  ├── v_funnel                                                    │
│  └── v_sync_health                                               │
└───────────────────────────────┬─────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   FastAPI (Python 3.12) │
                    │   GET /kpis/overview   │
                    │   GET /kpis/meta-ads   │
                    │   GET /kpis/bookings   │
                    │   GET /kpis/funnel     │
                    │   GET /kpis/sync-health│
                    └───────────┬────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   Next.js 14 (SSR)     │
                    │   revalidate: 60s      │
                    │   ├── /overview        │
                    │   ├── /meta-ads        │
                    │   ├── /rezdy           │
                    │   ├── /funnel          │
                    │   └── /health          │
                    └────────────────────────┘
```

## Camadas de dados

### 1. Raw (raw_events)
Tudo que entra de webhooks ou APIs é preservado em `jsonb` com:
- `payload_hash` para deduplicação perfeita
- `processing_status` para rastreamento do pipeline
- `received_at` para auditoria
- Nunca é deletado — serve como fonte de replay

### 2. Normalized (fact_* / dim_*)
Tabelas estruturadas com upsert idempotente:
- `fact_meta_ad_performance_daily`: um registro por (data, conta, campanha, adset, anúncio, janela de atribuição)
- `fact_rezdy_bookings`: um registro por `order_number` (chave natural da Rezdy)
- `fact_funnel_touchpoints`: ponte entre campanhas Meta e reservas Rezdy por UTM/campanha

### 3. Analytics (views SQL)
Views que calculam KPIs derivados na query time:
- Fórmulas centralizadas no banco
- Sem necessidade de job de aggregação
- Fácil de auditar e modificar

## Near realtime vs Realtime

| Fonte | Mecanismo | Latência típica |
|---|---|---|
| Meta Ads | Polling API a cada 30 min | 0–30 min |
| Rezdy novos pedidos | Webhook → transform | 2–10 seg |
| Rezdy reconciliação | Polling API 1x/dia | até 24h |

**Realtime genuíno** (via Supabase Realtime): é possível subscrever
`fact_rezdy_bookings` via Supabase e fazer o dashboard atualizar cards
automaticamente sem polling. Adicionar `supabase-js` no frontend e
usar `supabase.channel()` para isso é o próximo passo natural.

## Estratégia de atribuição

A tabela `fact_funnel_touchpoints` liga reservas Rezdy a campanhas Meta Ads por:

1. **UTM exato**: `utm_campaign` da reserva bate com `campaign_name` da campanha Meta
2. **Janela temporal**: reserva criada dentro de N dias após o último clique em campanhas Meta
3. Confiança: `exact_utm` > `temporal_window`

A janela é configurável via `attribution_window_days` (padrão: 7 dias).
