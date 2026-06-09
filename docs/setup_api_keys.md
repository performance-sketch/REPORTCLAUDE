# Configuração de Credenciais

## Meta Ads

### 1. Criar Meta App

1. Acesse [developers.facebook.com/apps](https://developers.facebook.com/apps)
2. Crie um novo app do tipo **Business**
3. Adicione o produto **Marketing API**
4. Copie `App ID` → `META_APP_ID`
5. Copie `App Secret` → `META_APP_SECRET`

### 2. Obter Access Token

**Opção A — System User (recomendado para produção):**
1. No Meta Business Manager → Configurações → Usuários do Sistema
2. Crie um System User com função Admin
3. Atribua acesso às contas de anúncios desejadas
4. Gere um token sem expiração com permissões `ads_read`, `ads_management`
5. Copie o token → `META_ACCESS_TOKEN`

**Opção B — Token de usuário (desenvolvimento):**
1. Use o [Graph API Explorer](https://developers.facebook.com/tools/explorer)
2. Selecione seu app → Gerar token
3. Permissões necessárias: `ads_read`, `read_insights`
4. Troque por um token de longa duração via endpoint `oauth/access_token`

### 3. Listar contas

```bash
curl "https://graph.facebook.com/v19.0/me/adaccounts?fields=account_id,name&access_token=SEU_TOKEN"
```

Copie os IDs (formato `act_XXXXXXX`) → `META_AD_ACCOUNT_IDS=act_111,act_222`

---

## Rezdy

### 1. Obter API Key

1. Acesse [app.rezdy.com/user/settings/apikey](https://app.rezdy.com/user/settings/apikey)
2. Copie a chave → `REZDY_API_KEY`

### 2. Configurar Webhook

1. Em Rezdy → Configurações → Webhooks
2. Endpoint: `https://SUA-API.com/webhooks/rezdy`
3. Eventos a ativar:
   - `order.created`
   - `order.updated`
   - `order.cancelled`
4. Defina um secret → `REZDY_WEBHOOK_SECRET`

---

## GitHub Secrets (para CI/CD)

Acesse **Settings → Secrets and variables → Actions** no repositório:

| Nome | Valor |
|---|---|
| `DATABASE_SYNC_URL` | URL do banco Postgres em produção |
| `META_ACCESS_TOKEN` | Token Meta Ads |
| `META_AD_ACCOUNT_IDS` | ex: `act_123,act_456` |
| `META_APP_ID` | ID do App Meta |
| `META_APP_SECRET` | Secret do App Meta |
| `REZDY_API_KEY` | Chave da Rezdy |
| `REZDY_WEBHOOK_SECRET` | Secret do webhook |
| `APP_SECRET_KEY` | Gerado com `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SYNC_TRIGGER_SECRET` | Idem |
| `API_URL` | URL base da API em prod (ex: `https://api.meusite.com`) |
| `NEXT_PUBLIC_API_URL` | URL pública (ex: `https://api.meusite.com`) |

---

## Variáveis de ambiente — produção

Nunca commite o arquivo `.env` real. Use o mecanismo de secrets do seu provider:

- **Railway**: variáveis em "Variables" do serviço
- **Render**: "Environment" do serviço
- **Fly.io**: `fly secrets set KEY=VALUE`
- **Supabase Edge Functions**: `supabase secrets set KEY=VALUE`
