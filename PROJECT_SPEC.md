# Sistema de Estacionamento Dom Pagamentos v2.0

Stack Railway | FastAPI + React + MySQL/PostgreSQL + Redis + Docker | Auth0 + Evolution API

---

## Contexto do sistema atual

O sistema atual (https://estacionamentodom.lovable.app) é um app React hospedado no Lovable.

**O que já existe:**
- Dashboard com seleção por andar (S2 - Subsolo 2, G2 - Garagem 2)
- Visualização de vagas individuais com status Livre / Ocupada
- Informação do ocupante: nome + veículo (ex: "Fiat - ARGO 1.0 6V Flex")
- Tags de posição: "Vaga de trás", "Parede"
- Botão "Ocupar Vaga" e "Veja o mapa das vagas"
- Autenticação com perfil de usuário
- Alternância de tema dark/light

**O que NÃO existe atualmente:**
- Suporte offline + sincronização
- Notificações WhatsApp / Email
- Reservas antecipadas
- Relatórios detalhados
- PWA instalável
- Histórico completo de movimentações
- Bot WhatsApp para consulta/reserva
- Registro de horário de entrada/saída

(Export estático do build Lovable atual está em `index.html`, `part.html`, `part.1.html` nesta pasta — apenas referência visual, não é código-fonte editável.)

---

## Objetivo v2.0

Sistema completo, inteligente e multicanal de gerenciamento de estacionamento, online e offline, com WhatsApp (Evolution API), autenticação corporativa (Auth0 + Google) e infraestrutura no Railway via Docker.

## Stack técnica

**Backend:** Python 3.12+, FastAPI (async), SQLAlchemy 2.x (asyncpg/aiomysql), Alembic, Pydantic v2, Uvicorn+Gunicorn, Redis (aioredis), Auth0 (JWT RS256).

**Frontend:** Vite 5+, React 18+ TS, Zustand + TanStack Query, Tailwind + shadcn/ui, Vite PWA Plugin (Workbox), Dexie.js (IndexedDB), @auth0/auth0-react, Axios.

**Banco:** Dev local = MySQL 8.x (Docker). Produção (Railway) = PostgreSQL 15+.

**Infra:** Railway, Docker por serviço, Evolution API v2 self-hosted (WhatsApp), Resend (email), Redis 7+ (Railway plugin), Railway Volumes para sessão WhatsApp.

## Regras críticas de compatibilidade MySQL ↔ PostgreSQL

1. NUNCA usar tipos dialect-specific (`mysql.TINYINT`, `postgresql.JSONB`) — sempre tipos genéricos SQLAlchemy: `Boolean`, `JSON`, `String`, `Integer`, `Text`, `DateTime`.
2. Nomes de tabela/coluna sempre snake_case lowercase.
3. Boolean nativo, nunca comparar com 0/1.
4. Upsert portátil via `session.merge()`, nunca `ON DUPLICATE KEY UPDATE`.
5. JSON como `Text` serializado, nunca `JSONB`.
6. Zero raw SQL dinâmico — sempre ORM.
7. `DATABASE_URL` via env var, trocando só o driver (`mysql+aiomysql://` ↔ `postgresql+asyncpg://`).
8. Testar `alembic upgrade head` antes de cada deploy.
9. Evolution API: volume persistente Railway em `/evolution/instances` (senão perde sessão WhatsApp a cada deploy).

## Autenticação (Auth0 + Google)

Login Google → Auth0 Universal Login → Post-Login Action valida domínio do email corporativo (bloqueia domínios não autorizados, com Management API deletando usuário criado se bloqueado) → JWT RS256 → FastAPI valida via JWKS Auth0 → RBAC (admin/operador) via custom claim.

**Desde a Fase 5**, a lista de domínios autorizados e de e-mails admin não é mais hardcoded na Action — vive no banco (tabelas `dominios_autorizados` e `admin_emails`, geridas pelo painel `/admin`) e a Action consulta via HTTP, autenticada por um segredo compartilhado (header `X-Internal-Secret`, configurado como Auth0 Secret `INTERNAL_API_SECRET` = `AUTH0_ACTION_SECRET` do backend):

```javascript
exports.onExecutePostLogin = async (event, api) => {
  const email = event.user.email;
  if (!email) { api.access.deny("Email não encontrado. Acesso negado."); return; }
  const domain = email.split("@")[1]?.toLowerCase();
  const headers = { "X-Internal-Secret": event.secrets.INTERNAL_API_SECRET };

  const respDominio = await fetch(`${event.secrets.API_URL}/admin/dominios/${domain}/verificar`, { headers });
  const { autorizado } = await respDominio.json();
  if (!autorizado) {
    api.access.deny(`Acesso restrito. O domínio @${domain} não está autorizado.`);
    return;
  }

  const respAdmin = await fetch(`${event.secrets.API_URL}/admin/admins/${encodeURIComponent(email)}/verificar`, { headers });
  const { admin } = await respAdmin.json();
  api.idToken.setCustomClaim("https://estacionamento.dom/role", admin ? "admin" : "operador");
};
```

O primeiro domínio/admin precisa ser inserido manualmente (`python -m scripts.seed_admin --dominio ... --admin ...`) antes de qualquer login funcionar — depois disso, o próprio painel `/admin` gerencia o resto.

Segurança backend obrigatória: CORS restrito (sem `*`), TrustedHostMiddleware em produção, rate limiting via Redis (fastapi-limiter), headers de segurança (X-Content-Type-Options, X-Frame-Options, HSTS), access tokens nunca em localStorage.

## Estrutura do projeto

Monorepo: `backend/` (FastAPI: main, config, database, security/auth+audit, models/{vaga,ocupante,reserva,movimentacao,audit_log}, schemas, routers/{vagas,reservas,movimentacoes,relatorios,webhook_whatsapp}, services/{whatsapp,email,redis_cache,sync}) + `frontend/` (Vite/React/TS: auth, api, components, pages, stores, hooks, offline/{db,sync}) + `evolution-api/` + `docker-compose.yml` raiz.

## Modelos principais (SQLAlchemy 2.x, tipos genéricos)

`Vaga` (id="S2-49", numero, andar, posicao, tipo, status enum livre/ocupada/reservada/manutencao, ativo, criado_em), `Ocupante` (vaga_id FK, nome, placa, veiculo, tipo_cliente enum mensalista/rotativo/visitante/prestador, hora_entrada, observacoes, operador_id=Auth0 sub), `Reserva` (vaga_id FK, nome, telefone, email, placa, inicio, fim, status, canal), `Movimentacao` (vaga_id FK, tipo entrada/saida/reserva, placa, motorista, veiculo, timestamp, operador_id, tempo_permanencia_min, sincronizado), `AuditLog` (usuario_id, acao, recurso, recurso_id, ip, timestamp, detalhes=JSON serializado em Text).

## PWA offline-first

Vite PWA Plugin (Workbox, NetworkFirst para API), Dexie.js com tabelas `operacoes` (fila de operações pendentes: tipo, vagaId, payload, timestamp, tentativas, sincronizado) e `vagasCache`. Listener `window.addEventListener('online', ...)` sincroniza fila pendente via `/movimentacoes/sync`.

## WhatsApp (Evolution API)

Deploy via template Railway (cria Evolution API + Postgres + Redis + volume `/evolution/instances`). Webhook `POST /webhook/whatsapp/{WHATSAPP_WEBHOOK_SECRET}` no FastAPI — o segredo no path autentica a chamada (404 para segredo incorreto); processa `messages.upsert`, ignora mensagens `fromMe`. Comandos: `/vagas`, `/vagas S2`, `/vagas G2`, `/reservar S2-49` (reserva por 2h), `/cancelar S2-49`, `/status ABC1234`, `/ajuda`. Telefone: prefixo `55` + sufixo `@s.whatsapp.net`.

## Email (Resend) e notificações automáticas

Confirmação e cancelamento de reserva (enviados por email e/ou WhatsApp, pulados quando a reserva já veio do canal WhatsApp, que confirma inline), relatório diário (`GET /relatorios/diario` para consulta admin, `POST /relatorios/diario/enviar` disparado por cron externo via header `X-Cron-Secret`), e vencimento de reserva (`POST /reservas/expirar-vencidas`, também via `X-Cron-Secret`, libera a vaga e notifica o cliente). Lembrete pré-reserva ainda não implementado — necessitaria de um novo campo no modelo `Reserva` e uma semântica mais clara do produto antes de construir.

## Checklist de segurança (antes de cada deploy)

Auth0 Post-Login Action testada bloqueando domínios não autorizados; JWT validado em toda rota autenticada; RBAC testado; tokens fora de localStorage; CORS sem wildcard; rate limiting ativo; inputs validados via Pydantic; sem stack trace exposto; zero raw SQL; AUTHENTICATION_API_KEY Evolution ≥32 chars aleatórios; volume WhatsApp persistente; webhook verificado; `.env` no `.gitignore`; secrets via env Railway; Postgres com backup automático + SSL; Redis com senha; Dockerfile sem segredos em layers.

## Fases de implementação

1. **Foundation** — monorepo, docker-compose (MySQL+Redis), FastAPI base + Alembic init/primeira migration, Auth0 tenant+Google+Post-Login Action, middleware JWT+RBAC, React Auth0Provider+rotas protegidas.
2. **Core Features** — CRUD vagas/movimentações/reservas, Dashboard (andares+mapa visual), formulário entrada/saída, cache Redis vagas (TTL 30s), WebSocket tempo real.
3. **Offline + PWA** — manifest+service worker, Dexie IndexedDB, fila de sync com retry, indicador online/offline, endpoint `/movimentacoes/sync`.
4. **WhatsApp + Email** — Evolution API Railway + volume, webhook + processador de comandos, Resend (confirmação/lembrete/relatório diário), notificações automáticas.
5. **Relatórios + Admin** — dashboard analítico (Recharts: status das vagas + histórico de entradas/saídas), exportação PDF (`GET /relatorios/diario/pdf`, weasyprint) e CSV (`GET /relatorios/movimentacoes/csv`), painel admin de domínios/e-mails admin (`/admin/dominios`, `/admin/admins`, com bootstrap via `scripts/seed_admin.py`), audit log viewer (`GET /admin/audit-logs`).
6. **Deploy Railway** — ver `DEPLOY.md` para o roteiro completo (não executável por mim sem acesso à conta Railway/Auth0/Evolution/Resend). O que foi construído e verificado localmente: Dockerfiles de produção multi-stage com usuário não-root e `HEALTHCHECK` (`backend/Dockerfile`, `frontend/Dockerfile`), normalização automática de `DATABASE_URL` (`postgres://`/`postgresql://`/`mysql://` sem driver → `+asyncpg`/`+aiomysql`, para colar a variável do plugin Railway sem editar), `/health` checando DB+Redis de verdade (503 se degradado), `backend/scripts/verify_db_compat.sh` (sobe MySQL e PostgreSQL reais em Docker, roda as migrations e um round-trip de Enum/Boolean em ambos — rodar antes de qualquer deploy que mude models), `railway.toml` por serviço (healthcheck + restart policy), CI no GitHub Actions (`.github/workflows/ci.yml`: pytest + build do frontend a cada push/PR — CD real depende de conectar o repo no dashboard Railway, que só você pode fazer).

## Regras gerais para o agent

1. Toda interface/mensagens/comentários em PT-BR.
2. Dark mode padrão, mobile-first, shadcn/ui, animações suaves.
3. Todas as rotas FastAPI e operações de banco `async/await`.
4. Tipos SQLAlchemy sempre genéricos, nunca dialect-specific.
5. Mensagens de erro claras ao usuário, sem detalhes internos.
6. `logging` estruturado, nunca `print()` em produção.
7. Evolution API: prefixo `55`, sufixo `@s.whatsapp.net`.
8. `alembic revision --autogenerate` após toda mudança em models.
9. pytest para rotas críticas; Jest para componentes React críticos.
10. Rodar checklist de segurança antes de cada fase de deploy.

*Versão: 2.0 | Atualizado: 2026-09-10*
