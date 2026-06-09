# Contratos de Dados

## Webhook Rezdy — Estrutura esperada

```json
{
  "event": "order.created",
  "booking": {
    "orderNumber": "VRXXXXXX",
    "status": "CONFIRMED",
    "totalAmount": 1485.54,
    "totalDue": 0,
    "totalPaid": 1485.54,
    "paymentOption": "CREDITCARD",
    "dateCreated": "2026-06-09T14:30:00Z",
    "dateUpdated": "2026-06-09T14:30:05Z",
    "customer": {
      "id": "CUST001",
      "firstName": "João",
      "lastName": "Silva",
      "email": "joao@exemplo.com",
      "phone": "+5521999999999"
    },
    "items": [
      {
        "productCode": "PROD01",
        "productName": "Doors off | 30min",
        "startTimeLocal": "2026-06-10T09:00:00",
        "endTimeLocal": "2026-06-10T09:30:00",
        "quantities": [
          { "optionLabel": "Adulto", "optionPrice": 742.77, "value": 2 }
        ]
      }
    ],
    "vouchers": [],
    "coupon": "CARIOQUINHA",
    "source": "ONLINE",
    "fields": [
      { "label": "utm_source", "value": "facebook" },
      { "label": "utm_campaign", "value": "lx_trafego" }
    ]
  }
}
```

**Eventos suportados:** `order.created`, `order.updated`, `order.cancelled`,
`booking.created`, `booking.updated`, `booking.cancelled`

## Meta Ads Insights — Estrutura esperada

```json
{
  "data": [
    {
      "date_start": "2026-06-09",
      "date_stop": "2026-06-09",
      "account_id": "2613909812239242",
      "account_name": "Vertical Rio Ads account",
      "campaign_id": "123456789",
      "campaign_name": "[LX][TRAFEGO][ABO][FRIO]",
      "adset_id": "987654321",
      "adset_name": "Público Frio 18-45",
      "ad_id": "111222333",
      "ad_name": "Video_v1",
      "impressions": "10000",
      "reach": "8500",
      "frequency": "1.18",
      "clicks": "500",
      "inline_link_clicks": "480",
      "landing_page_views": "310",
      "spend": "150.25",
      "cpc": "0.30",
      "cpm": "15.02",
      "ctr": "5.00",
      "actions": [
        { "action_type": "link_click", "value": "480" },
        { "action_type": "purchase", "value": "2" }
      ],
      "action_values": [
        { "action_type": "purchase", "value": "2971.08" }
      ]
    }
  ],
  "paging": {
    "cursors": { "before": "...", "after": "..." },
    "next": "https://graph.facebook.com/..."
  }
}
```

## Idempotência

### Webhooks Rezdy
- `payload_hash = SHA256(source + event_type + payload_json_canonico)`
- `UNIQUE(source, event_type, payload_hash)` na `raw_events`
- Segundo webhook idêntico → `ON CONFLICT DO NOTHING` → retorna 202 normalmente

### Meta Ads upsert
- `UNIQUE(date, account_id, campaign_id, adset_id, ad_id, attribution_window)`
- `ON CONFLICT DO UPDATE` atualiza todos os campos exceto a chave natural

### Rezdy bookings upsert
- `UNIQUE(order_number)` na `fact_rezdy_bookings`
- `ON CONFLICT DO UPDATE` — sempre reflete o estado mais recente

## Contratos das tabelas

### raw_events
| Campo | Tipo | Obrigatório | Notas |
|---|---|---|---|
| `source` | text | sim | `meta_ads` ou `rezdy` |
| `event_type` | text | sim | ex: `order.created` |
| `payload` | jsonb | sim | Payload bruto sem modificação |
| `payload_hash` | text(64) | sim | SHA256 para deduplicação |
| `processing_status` | text | sim | `pending`, `processed`, `error`, `skipped` |

### fact_meta_ad_performance_daily
Chave natural: `(date, account_id, campaign_id, adset_id, ad_id, attribution_window)`
Todos os campos numéricos são `NUMERIC` (não `FLOAT`) para evitar perda de precisão monetária.

### fact_rezdy_bookings
Chave natural: `order_number` (número único de pedido da Rezdy).
Campos de UTM são populados a partir de `booking.fields[]` quando disponíveis.
