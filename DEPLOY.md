# Deploy no Railway

Este documento é o roteiro exato para colocar o sistema no ar. Eu (agente) não tenho
acesso à sua conta Railway/Auth0/Evolution API/Resend — os passos abaixo precisam ser
executados por você no painel de cada serviço. Tudo que podia ser verificado sem essas
credenciais (Dockerfiles, migrations, compatibilidade MySQL↔PostgreSQL, CI) já foi
testado localmente — ver `PROJECT_SPEC.md` e o histórico de commits.

## 1. Pré-requisitos (fora do Railway)

Antes de tocar no Railway, você precisa ter em mãos:

- **Auth0**: um tenant com Google Social Connection habilitada, a Post-Login Action
  atualizada (script em `PROJECT_SPEC.md` § Autenticação), e o `AUTH0_DOMAIN`/
  `AUTH0_AUDIENCE`/`AUTH0_CLIENT_ID` da SPA.
- **Evolution API**: pode ser deployada como um serviço Railway separado (ver §4) —
  não precisa de conta externa, mas precisa escanear o QR code do WhatsApp da empresa
  depois do deploy.
- **Resend**: uma API key (grátis até 3.000 emails/mês) e um domínio de envio
  verificado (ou use o domínio de sandbox deles para testar).

## 2. Criar o projeto Railway

1. `railway.app` → **New Project** → **Empty Project** (não use um template pronto —
   vamos adicionar os serviços um a um para ter controle sobre cada Dockerfile).
2. Dentro do projeto, adicione os plugins de banco de dados:
   - **+ New** → **Database** → **PostgreSQL**
   - **+ New** → **Database** → **Redis**

## 3. Serviço backend

1. **+ New** → **GitHub Repo** → selecione `GGT-dev-tech/controle-estacionamento-dom`.
2. Nas configurações do serviço (**Settings**):
   - **Root Directory**: `backend`
   - Railway detecta `backend/railway.toml` automaticamente (builder Dockerfile,
     healthcheck em `/health`).
3. Em **Variables**, adicione (ou vincule via referência de outro serviço):

   ```
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   REDIS_URL=${{Redis.REDIS_URL}}
   ENVIRONMENT=production
   PORT=8000
   FRONTEND_URL=https://<seu-dominio-frontend>
   API_HOST=<seu-dominio-backend>.up.railway.app

   AUTH0_DOMAIN=<seu-tenant>.auth0.com
   AUTH0_AUDIENCE=https://api.estacionamento.dom

   EVOLUTION_API_URL=https://<seu-servico-evolution>.up.railway.app
   EVOLUTION_API_KEY=<chave forte, min 32 chars>
   EVOLUTION_INSTANCE_NAME=dom-estacionamento
   WHATSAPP_WEBHOOK_SECRET=<chave forte, min 32 chars>

   RESEND_API_KEY=<sua chave Resend>
   EMAIL_FROM=noreply@seudominio.com
   RELATORIO_DESTINATARIOS=admin@seudominio.com

   CRON_SECRET=<chave forte, min 32 chars>
   AUTH0_ACTION_SECRET=<chave forte, min 32 chars>
   ```

   > **Importante**: `${{Postgres.DATABASE_URL}}` do Railway vem como
   > `postgresql://user:pass@host:port/db` (sem `+asyncpg`). O backend normaliza isso
   > sozinho (`app/config.py`, `_normalizar_driver_async`) — cole a variável como o
   > Railway fornece, sem editar.

4. Deploy. Acompanhe os logs — a primeira inicialização roda `alembic upgrade head`
   automaticamente (é o `CMD` do `backend/Dockerfile`).
5. **Bootstrap do primeiro admin** (obrigatório uma única vez — sem isso ninguém
   consegue logar, porque nenhum domínio está autorizado ainda):

   ```
   railway run --service backend python -m scripts.seed_admin \
     --dominio seudominio.com --admin voce@seudominio.com
   ```

   (Ou `railway shell` e rode o comando de dentro do container.)

## 4. Serviço Evolution API (WhatsApp)

1. **+ New** → **Template** → busque "Evolution API" (cria o container + um Postgres
   próprio + Redis próprio automaticamente).
2. Configure as variáveis do template (ver `PROJECT_SPEC.md` § WhatsApp para a lista
   completa). O campo que mais importa:

   ```
   WEBHOOK_GLOBAL_URL=https://<seu-backend>.up.railway.app/webhook/whatsapp/<WHATSAPP_WEBHOOK_SECRET>
   ```

   Use o **mesmo** valor de `WHATSAPP_WEBHOOK_SECRET` configurado no serviço backend.
3. **Crítico**: confirme que existe um **Railway Volume** montado em
   `/evolution/instances`. Sem isso, a sessão do WhatsApp (QR code escaneado) some a
   cada redeploy.
4. Acesse `https://<evolution>.up.railway.app/manager`, crie uma instância chamada
   `dom-estacionamento` (mesmo valor de `EVOLUTION_INSTANCE_NAME`), escaneie o QR
   code com o WhatsApp da empresa.

## 5. Serviço frontend

1. **+ New** → **GitHub Repo** → mesmo repositório.
2. **Root Directory**: `frontend`.
3. Em **Variables** (essas são build args do `frontend/Dockerfile` — o Railway as
   injeta automaticamente no build quando têm o mesmo nome do `ARG`):

   ```
   VITE_API_URL=https://<seu-backend>.up.railway.app
   VITE_AUTH0_DOMAIN=<seu-tenant>.auth0.com
   VITE_AUTH0_CLIENT_ID=<client id da SPA no Auth0>
   VITE_AUTH0_AUDIENCE=https://api.estacionamento.dom
   ```

4. Deploy. Depois, volte no serviço **backend** e atualize `FRONTEND_URL` para a URL
   real gerada (o CORS do backend é restrito a essa origem exata).
5. No Auth0, adicione a URL do frontend em **Allowed Callback URLs**,
   **Allowed Logout URLs** e **Allowed Web Origins**.

## 6. Tarefas agendadas (Railway Cron)

Duas rotinas usam o header `X-Cron-Secret` (mesmo valor de `CRON_SECRET`):

| Rotina | Endpoint | Sugestão de frequência |
|---|---|---|
| Expirar reservas vencidas | `POST /reservas/expirar-vencidas` | a cada 15 min |
| Relatório diário por email | `POST /relatorios/diario/enviar` | 1x/dia, ex. 8h |

No Railway: **+ New** → **Cron Job**, aponte para o serviço backend, comando tipo:
```
curl -X POST -H "X-Cron-Secret: $CRON_SECRET" https://<backend>.up.railway.app/reservas/expirar-vencidas
```

## 7. Auth0 Post-Login Action

Cole o script atualizado de `PROJECT_SPEC.md` § Autenticação no Auth0 Dashboard
(**Actions** → **Flows** → **Login** → arraste a Action customizada). Configure os
**Secrets** da Action:

```
API_URL = https://<seu-backend>.up.railway.app
INTERNAL_API_SECRET = <mesmo valor de AUTH0_ACTION_SECRET do backend>
```

## 8. Verificação pós-deploy

- [ ] `GET /health` do backend retorna `{"status":"ok","database":"ok","redis":"ok"}`
- [ ] Login com um email do domínio cadastrado funciona; com um domínio não
      cadastrado é bloqueado
- [ ] `/admin` no frontend mostra o painel (logado como o admin do bootstrap)
- [ ] `/vagas` no WhatsApp responde
- [ ] Uma reserva criada pelo webapp dispara email de confirmação (se `RESEND_API_KEY`
      configurada)
- [ ] Checklist de segurança completo em `PROJECT_SPEC.md` § Checklist de segurança

## 9. Antes de qualquer deploy que mude models/migrations

Rode localmente:
```
cd backend && ./scripts/verify_db_compat.sh
```
Isso sobe MySQL e PostgreSQL reais em Docker, roda `alembic upgrade head` e um
round-trip de Enum/Boolean em ambos — pega problemas de compatibilidade de dialeto
antes de chegarem em produção.

## 10. Monitoramento e alertas de disponibilidade

O Railway já reinicia o serviço automaticamente se `/health` falhar
(`restartPolicyType = ON_FAILURE` em `railway.toml`). Isso cobre "monitoramento",
mas não "alertas" — para ser avisado quando o serviço cair, configure um monitor
externo gratuito apontando para `GET /health` (qualquer um serve; nenhum foi
configurado aqui por exigir uma conta que eu não tenho):

- **UptimeRobot** (grátis, mais simples) ou **Better Stack/Uptime** — monitor HTTP
  em `https://<backend>.up.railway.app/health`, alerta se status ≠ 200, checagem a
  cada 1–5 min, notificação por email/Slack/WhatsApp.
