# Dicionário de KPIs

## Meta Ads

| KPI | Fórmula | Origem | Notas |
|---|---|---|---|
| **Spend** | — | `fact_meta_ad_performance_daily.spend` | Moeda da conta |
| **Impressões** | — | `.impressions` | |
| **Alcance** | — | `.reach` | Pessoas únicas |
| **Frequência** | `impressions / reach` | Calculado | |
| **Cliques** | — | `.clicks` | Todos os cliques |
| **Link Clicks** | — | `.link_clicks` | Cliques em links |
| **LPV** | — | `.landing_page_views` | Landing page views |
| **CTR** | `clicks / impressions` | Calculado | |
| **CPC** | `spend / clicks` | Calculado | |
| **CPM** | `spend × 1000 / impressions` | Calculado | |
| **Leads** | — | `actions[lead]` | |
| **Purchases** | — | `actions[purchase]` | Pixel |
| **Conversion Value** | — | `action_values[purchase]` | |
| **CPA** | `spend / conversions` | Calculado | |
| **ROAS Meta** | `conversion_value / spend` | Calculado | Baseado no Pixel |

## Rezdy

| KPI | Fórmula | Origem | Notas |
|---|---|---|---|
| **Reservas Criadas** | — | `COUNT(*)` | Todos os status |
| **Reservas Confirmadas** | — | `WHERE status = 'CONFIRMED'` | |
| **Reservas Canceladas** | — | `WHERE status IN ('CANCELLED','ABANDONED_CART')` | |
| **Receita Bruta** | — | `SUM(gross_revenue)` | |
| **Receita Confirmada** | — | `SUM(gross_revenue) WHERE CONFIRMED` | |
| **Ticket Médio** | `confirmed_revenue / confirmed_count` | Calculado | |
| **PAX** | — | `SUM(quantity)` | Total de participantes |
| **Taxa Cancelamento** | `cancelled / created` | Calculado | |

## KPIs Integrados (funil Meta → Rezdy)

| KPI | Fórmula | Notas |
|---|---|---|
| **ROAS Real** | `confirmed_rezdy_revenue / meta_spend` | Principal KPI do dashboard |
| **CAC** | `meta_spend / confirmed_bookings` | Custo de aquisição por reserva confirmada |
| **Clique → Reserva** | `bookings_created / clicks` | Taxa de conversão do clique |
| **Clique → Confirmação** | `confirmed_bookings / clicks` | Taxa de conversão final |
| **Custo / Reserva Criada** | `meta_spend / bookings_created` | |
| **Custo / Reserva Conf.** | `meta_spend / confirmed_bookings` | |
| **Receita / Clique** | `confirmed_revenue / clicks` | |

## Janela de Atribuição

A atribuição entre cliques Meta e reservas Rezdy usa:

1. **UTM exato** (`utm_campaign` da reserva = `campaign_name` do Meta) → confiança `high`
2. **Janela temporal** (reserva criada N dias após clique em campanha ativa) → confiança `medium`

O parâmetro `attribution_window_days` (padrão: 7) é configurável por consulta.

## Regras de negócio

- Reservas com status `ABANDONED_CART` são contadas como **criadas mas não confirmadas**
- O cálculo de ROAS Real usa **receita confirmada**, não receita total (inclui abandonos)
- Meta Ads reporta dados com atraso de atribuição de até 28 dias; o full backfill diário corrige isso
- `fact_meta_ad_performance_daily` tem granularidade por anúncio (`ad_id`); para agregações por campanha, some os registros
