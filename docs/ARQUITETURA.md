# Documentação Técnica de Arquitetura — Sistema de Estacionamento Dom Pagamentos v2.0

> **Metodologia.** Este documento foi produzido por leitura integral do código-fonte presente no
> repositório em `2026-09-10` (commits até `9a1f3f6`), não a partir do `PROJECT_SPEC.md` ou de
> suposições sobre o que "deveria" existir. Toda afirmação é rastreável a um arquivo específico,
> citado como `caminho/arquivo.ext:linha`. Quando o código diverge do que o `PROJECT_SPEC.md`
> descreve como intenção, ou quando alguma informação não pôde ser determinada apenas pela leitura
> estática do código (comportamento de infraestrutura externa — Auth0, Railway, Evolution API —, ou
> decisões que dependem de acesso a esses painéis), isso é sinalizado explicitamente na seção
> [Limitações, Divergências e Perguntas em Aberto](#limitações-divergências-e-perguntas-em-aberto),
> em vez de ser assumido.
>
> Os diagramas estão em [PlantUML](https://plantuml.com/) válido, prontos para renderização (VS Code
> com a extensão PlantUML, IntelliJ, `plantuml.jar`, ou um servidor PlantUML). Cada bloco é
> autocontido (``@startuml``/``@enduml``).

## Sumário

1. [Visão geral da arquitetura](#1-visão-geral-da-arquitetura)
2. [Stack tecnológica](#2-stack-tecnológica)
3. [Backend](#3-backend)
4. [Frontend](#4-frontend)
5. [Banco de dados](#5-banco-de-dados)
6. [Infraestrutura e deploy](#6-infraestrutura-e-deploy)
7. [Diagramas UML obrigatórios](#7-diagramas-uml-obrigatórios)
8. [Diagramas de fluxo de dados](#8-diagramas-de-fluxo-de-dados)
9. [Limitações, divergências e perguntas em aberto](#limitações-divergências-e-perguntas-em-aberto)

---

## 1. Visão geral da arquitetura

O sistema é um **monólito modular de dois processos** (API + SPA), cada um empacotado como um
container Docker independente, acompanhado de dois serviços gerenciados (PostgreSQL/MySQL e Redis)
e integrações externas via HTTP com três SaaS (Auth0, Evolution API/WhatsApp, Resend/e-mail). Não há
microsserviços internos: todo o domínio de negócio (vagas, ocupantes, reservas, movimentações,
auditoria, administração) vive em um único processo FastAPI.

```plantuml
@startuml Visao_Geral
!pragma layout smetana
skinparam componentStyle rectangle
title Visão geral da arquitetura — Sistema de Estacionamento Dom Pagamentos

actor "Operador / Admin\n(navegador)" as usuario
actor "Cliente WhatsApp" as cliente_wa

package "Frontend — SPA (Vite + React + TS)" as frontend {
  [React Router\n+ Páginas] as spa
  [Dexie / IndexedDB\n(fila offline + cache)] as dexie
  [Service Worker\n(Workbox)] as sw
}

package "Backend — FastAPI (Python 3.12, async)" as backend {
  [Routers\n(Controllers)] as routers
  [Services\n(regras de negócio)] as services
  [Modelos SQLAlchemy\n(ORM)] as orm
  [WebSocket Manager] as wsmanager
}

database "PostgreSQL (prod)\n/ MySQL (dev)" as db
database "Redis" as redis

cloud "Auth0\n(OIDC / JWT RS256)" as auth0
cloud "Evolution API\n(WhatsApp self-hosted)" as evolution
cloud "Resend\n(e-mail transacional)" as resend
cloud "Railway Cron\n(scheduler externo)" as cron

usuario --> spa : HTTPS
spa --> sw
spa <--> dexie : IndexedDB (offline)
spa --> routers : REST (Axios + JWT Bearer)
spa <..> wsmanager : WebSocket /ws/vagas (tempo real)

routers --> services
services --> orm
orm --> db : SQL (asyncpg / aiomysql)
routers ..> redis : cache de /vagas (TTL 30s)
services ..> redis : invalidação de cache

spa ..> auth0 : login (Auth0 Universal Login)
routers ..> auth0 : valida JWT via JWKS
auth0 ..> routers : Post-Login Action\n(GET /admin/*/verificar,\nheader X-Internal-Secret)

cliente_wa <..> evolution : WhatsApp
evolution --> routers : webhook POST /webhook/whatsapp/{secret}
services --> evolution : envio de mensagens (REST)
services --> resend : e-mails de reserva/relatório

cron --> routers : POST /reservas/expirar-vencidas\nPOST /relatorios/diario/enviar\n(header X-Cron-Secret)
@enduml
```

**Raciocínio de identificação:** a separação em dois processos é evidenciada por dois `Dockerfile`
distintos (`backend/Dockerfile`, `frontend/Dockerfile`) e dois serviços Railway distintos
(`backend/railway.toml`, `frontend/railway.toml`, ver `DEPLOY.md:30-117`). A ausência de
microsserviços internos é confirmada pela estrutura de um único `app` FastAPI (`backend/app/main.py`)
que importa e registra todos os routers do domínio em um só processo (`backend/app/main.py:68-74`).

---

## 2. Stack tecnológica

| Tecnologia | Onde é usada | Por que foi escolhida (evidência no código) | Problema que resolve | Interações / dependências |
|---|---|---|---|---|
| **Python 3.12 + FastAPI** (`fastapi==0.115.6`) | `backend/app/*` | Framework ASGI assíncrono; toda rota é `async def` (`app/routers/*.py`) | Serve a API REST e o endpoint WebSocket no mesmo processo | Uvicorn/Gunicorn como servidor; Pydantic para validação |
| **SQLAlchemy 2.x (async)** + `asyncpg`/`aiomysql` | `backend/app/models`, `app/database.py` | ORM com suporte assíncrono nativo (`AsyncSession`, `create_async_engine`) | Abstrai o dialeto de banco (MySQL dev / PostgreSQL prod) atrás de uma única API | Alembic depende do mesmo `Base.metadata`; `asyncpg` usado em produção, `aiomysql`/`pymysql` em dev |
| **Alembic** | `backend/alembic/` | Migração de schema versionada, `env.py` roda contra o engine assíncrono | Evolução controlada do schema entre MySQL e PostgreSQL | Depende de `app.config.settings.database_url` e de todos os módulos de `app.models` serem importados para registro dos metadados |
| **Pydantic v2** (`pydantic-settings`) | `backend/app/schemas`, `app/config.py` | DTOs de entrada/saída desacoplados dos modelos ORM; `Settings` carrega variáveis de ambiente com validação (`field_validator`) | Validação de payload e normalização de configuração (ex.: `DATABASE_URL`) | Consumido por todos os routers via `response_model=` |
| **Redis** (`redis==5.2.1`, `redis.asyncio`) | `backend/app/services/redis_cache.py` | Cliente assíncrono, com captura de `RedisError` em todo ponto de uso | Cache de leitura de `/vagas` (TTL 30s) e checagem de disponibilidade em `/health` | Consumido pelos routers de `vagas` e invalidado pelos serviços de `sync.py` |
| **PyJWT + JWKS (Auth0)** | `backend/app/security/auth.py` | `PyJWKClient` busca a chave pública do tenant Auth0 dinamicamente; valida RS256, audience e issuer | Autenticação stateless sem o backend guardar senhas/sessions | Usado por toda rota protegida (`Depends(get_current_user)`/`Depends(require_role(...))`) e pelo endpoint WebSocket |
| **httpx** | `backend/app/services/whatsapp.py` | Cliente HTTP assíncrono para chamar a Evolution API | Envio de mensagens WhatsApp e leitura do webhook recebido | Depende de `EVOLUTION_API_URL`/`EVOLUTION_API_KEY` |
| **resend** (SDK) | `backend/app/services/email.py` | Envio de e-mails transacionais (confirmação/cancelamento de reserva, relatório diário) | Notificação por e-mail sem gerir SMTP próprio | Templates HTML em `email_templates.py` |
| **weasyprint** | `backend/app/routers/relatorios.py:8,57` | Renderiza HTML → PDF para `GET /relatorios/diario/pdf` | Exportação de relatório em PDF sem dependência de um serviço externo | Exige libs nativas (`pango`, `cairo`, `gdk-pixbuf`) instaladas na imagem Docker (`backend/Dockerfile:22-30`) |
| **Gunicorn + Uvicorn workers** | `backend/Dockerfile:42-44` | `gunicorn` gerencia 4 processos `uvicorn.workers.UvicornWorker` | Paralelismo de processos para ASGI em produção | Substitui o `uvicorn --reload` usado em dev (`docker-compose.yml:42`) |
| **Vite 6 + React 18 + TypeScript** | `frontend/src/*` | Build tool + framework de UI tipado | SPA responsiva, mobile-first | `vite-plugin-pwa` para PWA; `@vitejs/plugin-react` |
| **TanStack Query v5** | `frontend/src/hooks/*` | Cache de estado de servidor com invalidação declarativa | Sincroniza dados remotos (vagas, reservas, relatórios) com a UI, com refetch sob demanda | Combinado com Dexie para fallback offline (`hooks/useVagas.ts:14-22`) |
| **Zustand** | `frontend/src/stores/useUiStore.ts` | Estado de UI mínimo (andar selecionado) — não persiste, não sincroniza com servidor | Estado local simples sem boilerplate de Context API | Consumido por `Home.tsx` e `ReservaForm` (indiretamente via `useVagas`) |
| **Dexie.js (IndexedDB)** | `frontend/src/offline/db.ts` | Banco local no navegador com duas tabelas: `operacoes` (fila) e `vagasCache` (fallback de leitura) | Suporte offline-first: grava operações pendentes e serve leituras quando a API está inacessível | `dexie-react-hooks` (`useLiveQuery`) usado em `StatusConexao.tsx` |
| **Axios** | `frontend/src/api/client.ts` | Instância única com interceptor de request que injeta `Authorization: Bearer <JWT>` | Centraliza autenticação de todas as chamadas REST | Token fornecido via `useApiToken` (Auth0 `getAccessTokenSilently`) |
| **@auth0/auth0-react** | `frontend/src/auth/*` | `Auth0Provider` com `cacheLocation="memory"` e `useRefreshTokens` | Login via Google/Auth0 Universal Login sem guardar token em `localStorage` | `withAuthenticationRequired` protege rotas; claim customizado `https://estacionamento.dom/role` define RBAC no cliente |
| **react-router-dom v7** | `frontend/src/App.tsx` | Roteamento client-side da SPA | Navegação entre Login/Home/Reservas/Relatórios/Admin | `RequireAdmin` e `withProtection` compõem guards de rota |
| **Recharts** | `frontend/src/components/charts/*` | Gráficos de barra (status das vagas) e linha (histórico de entradas/saídas) | Visualização analítica no painel de relatórios | Consome os DTOs de `api/relatorios.ts` |
| **shadcn/ui (+ Radix + CVA)** | `frontend/src/components/ui/*` | Primitivos de UI (`button`, `dialog`, `input`, `select`, `badge`, `label`) | Componentes acessíveis e estilizáveis via Tailwind | `class-variance-authority` para variantes (ex.: `Badge` por status de vaga) |
| **Tailwind CSS** | `tailwind.config.ts`, `index.css` | Estilização utilitária, dark mode padrão | Consistência visual mobile-first | `tailwind-merge`/`clsx` via util `cn()` |
| **vite-plugin-pwa (Workbox)** | `vite.config.ts:2,9-37` | Manifest + service worker gerado automaticamente, cache `NetworkFirst` para a API | Instalabilidade (PWA) e cache de rede | Ver observação sobre o regex de `urlPattern` na seção de limitações |
| **Docker (multi-stage)** | `backend/Dockerfile`, `frontend/Dockerfile` | Build reprodutível, imagem final enxuta, usuário não-root, `HEALTHCHECK` | Empacotamento para deploy no Railway | `railway.toml` aponta para o `Dockerfile` de cada serviço |
| **Railway** | `backend/railway.toml`, `frontend/railway.toml`, `DEPLOY.md` | PaaS com plugins gerenciados de Postgres/Redis, healthcheck e restart automático | Hospedagem de produção sem gerenciar servidores | Variáveis de ambiente injetadas via dashboard Railway |
| **Evolution API** (self-hosted, v2.1.1) | `evolution-api/docker-compose.yml` (dev), template Railway (prod) | Gateway WhatsApp não-oficial (Baileys) | Canal de consulta/reserva via WhatsApp sem custo de API oficial | Requer volume persistente para a sessão do WhatsApp |
| **GitHub Actions** | `.github/workflows/ci.yml` | CI: `pytest` (backend) + `npm run build` (frontend) a cada push/PR em `main` | Garante que testes passam e o frontend compila antes do merge | Não faz deploy (CD é manual, ver seção 6) |

---

## 3. Backend

### 3.1 Estrutura de pastas

```text
backend/
├── app/
│   ├── main.py            # bootstrap FastAPI, middlewares, /health, registro de routers
│   ├── config.py          # Settings (pydantic-settings) — variáveis de ambiente
│   ├── database.py        # engine assíncrono + sessionmaker + dependency get_db
│   ├── models/             # entidades ORM (SQLAlchemy declarative)
│   ├── schemas/             # DTOs de entrada/saída (Pydantic)
│   ├── routers/             # controllers HTTP (um router por recurso)
│   ├── security/             # autenticação JWT, RBAC, auditoria
│   └── services/             # regras de negócio, integrações externas, cache, WebSocket
├── alembic/                 # migrações de schema
├── scripts/                 # scripts operacionais (bootstrap admin, smoke test de compat.)
└── tests/                   # pytest + httpx.AsyncClient + SQLite em memória
```

### 3.2 Camadas — o que existe e o que **não** existe

O backend segue uma estrutura em camadas pragmática, **não** uma Clean Architecture/DDD estrita com
Repository/UseCase/Entidade de domínio explícitos. É importante documentar isso com precisão, pois o
enunciado deste levantamento pede casos de uso, repositórios e entidades como elementos a identificar:

| Camada solicitada | O que existe de fato | Evidência |
|---|---|---|
| **Presentation / Controllers** | `app/routers/*.py` — um `APIRouter` por recurso, contendo validação de entrada (via `response_model`/tipos de parâmetro) e orquestração da resposta HTTP | `app/routers/vagas.py`, `reservas.py`, `movimentacoes.py`, `relatorios.py`, `admin.py`, `webhook_whatsapp.py`, `ws.py` |
| **Casos de uso / Application** | Não há classes `UseCase` dedicadas. As regras de negócio de transição de estado (ocupar, liberar, reservar, cancelar, expirar) estão implementadas como **funções de módulo** em `app/services/sync.py`, que fazem o papel de caso de uso: recebem DTO + identidade do operador, aplicam a regra, persistem e disparam efeitos colaterais (cache, WebSocket) | `app/services/sync.py:24-195` |
| **Domínio / Entidades** | Não há um modelo de domínio separado da persistência. As classes SQLAlchemy em `app/models/*.py` acumulam o papel de entidade de domínio **e** de mapeamento ORM — são "anêmicas": não contêm métodos de comportamento, apenas atributos tipados. As regras (transições de `StatusVaga`, validade de datas de reserva) vivem fora da entidade, em `services/sync.py` e em validadores Pydantic | `app/models/vaga.py`, `app/schemas/reserva.py:14-20` |
| **Repositórios** | **Não identificado.** Não existe uma classe/interface `VagaRepository`, `ReservaRepository` etc. O acesso a dados é feito diretamente via `AsyncSession` (`db.get(...)`, `select(...)`) tanto dentro dos routers (leituras simples) quanto dentro dos serviços (escritas com regra de negócio). A `AsyncSession` do SQLAlchemy cumpre informalmente o papel de gateway de persistência | Presente em praticamente todo router e em `services/sync.py` |
| **DTOs** | Bem definidos e separados dos modelos ORM: `app/schemas/*.py` (`VagaCreate`/`VagaRead`/`VagaComDetalhes`, `ReservaCreate`/`ReservaRead`, `EntradaCreate`/`SaidaCreate`/`MovimentacaoRead`, DTOs de sincronização e de admin) | `app/schemas/` |
| **ORM** | SQLAlchemy 2.0 estilo declarativo (`Mapped[]`/`mapped_column`), com tipos genéricos (não dialect-specific), conforme regra do `PROJECT_SPEC.md` — **confirmado como seguido** em todos os modelos lidos | `app/models/*.py` |
| **Migrações** | Alembic, cadeia linear `0001` → `0002` | `backend/alembic/versions/` |
| **Middlewares** | CORS restrito a uma única origem, `TrustedHostMiddleware` (só em produção), middleware customizado de cabeçalhos de segurança | `app/main.py:22-42` |
| **Autenticação/Autorização** | JWT RS256 validado contra o JWKS do Auth0; RBAC via claim customizado `https://estacionamento.dom/role`, com dependência `require_role(*roles)` | `app/security/auth.py` |
| **Tratamento de erros** | Duas exceções de domínio (`RecursoNaoEncontradoError`, `ConflitoOperacaoError`) capturadas nos routers e convertidas em `HTTPException(404)`/`HTTPException(409)`. **Não há um exception handler global registrado** (`@app.exception_handler`) — erros de validação Pydantic caem no `422` padrão do FastAPI, e exceções não previstas caem no `500` padrão do Starlette (sem stack trace exposto ao cliente, mas também sem um formato de erro customizado) | Ausência verificada em `app/main.py` (nenhum `add_exception_handler`/`exception_handler`) |
| **Validações** | Pydantic v2 (`field_validator`), ex.: `ReservaBase.fim_apos_inicio` garante `fim > inicio` | `app/schemas/reserva.py:14-20` |
| **Logs** | Módulo `logging` padrão da stdlib, `basicConfig(level=INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")` configurado uma vez em `main.py`; loggers de módulo (`logging.getLogger(__name__)`) usados em `movimentacoes.py`, `webhook_whatsapp.py`, `ws.py`, `whatsapp.py`, `email.py`, `redis_cache.py`, `ws_manager.py`, `security/audit.py` | `app/main.py:15-18` |
| **Cache** | Redis, somente para a listagem de vagas (`GET /vagas`), TTL de 30s, com invalidação ativa em toda escrita relevante | `app/services/redis_cache.py` |

### 3.3 Routers (Controllers) — responsabilidades

| Router | Prefixo | Rotas | Responsabilidade |
|---|---|---|---|
| `vagas.py` | `/vagas` | `GET /`, `GET /{id}`, `POST /` (admin), `PATCH /{id}` (admin), `DELETE /{id}` (admin, soft-delete) | CRUD de vagas; monta `VagaComDetalhes` combinando `Vaga` + `Ocupante` atual + `Reserva` ativa; usa cache Redis na listagem |
| `reservas.py` | `/reservas` | `GET /`, `POST /`, `POST /{id}/cancelar`, `POST /expirar-vencidas` (cron) | Orquestra `services/sync.py` para criar/cancelar reservas; dispara notificações; expira reservas vencidas via chamada de cron externo |
| `movimentacoes.py` | `/movimentacoes` | `GET /`, `POST /entrada`, `POST /saida`, `POST /sync` | Registra entrada/saída; **endpoint central de reconciliação offline** — aplica em lote as operações enfileiradas no Dexie do cliente, tolerando falha parcial por item |
| `relatorios.py` | `/relatorios` | `GET /diario`, `GET /historico`, `POST /diario/enviar` (cron), `GET /diario/pdf`, `GET /movimentacoes/csv` | Agregações analíticas (somente admin) e exportação PDF/CSV |
| `admin.py` | `/admin` | CRUD de `dominios_autorizados`, CRUD de `admin_emails`, rotas `/verificar` (consumidas pela Auth0 Action), `GET /audit-logs` | Administração do controle de acesso por domínio de e-mail e visualização de auditoria |
| `webhook_whatsapp.py` | `/webhook` | `POST /whatsapp/{secret}` | Recebe eventos da Evolution API, filtra `messages.upsert` não enviadas por mim mesmo (`fromMe`), delega ao processador de comandos |
| `ws.py` | — | `WS /ws/vagas` | Canal de tempo real; valida o JWT recebido via query string antes de aceitar a conexão |

### 3.4 Services — responsabilidades

| Módulo | Responsabilidade |
|---|---|
| `sync.py` | **Núcleo de regras de negócio** (caso de uso): `aplicar_entrada`, `aplicar_saida`, `aplicar_reserva`, `aplicar_cancelamento`, `expirar_reservas_vencidas`. Cada função valida pré-condições de estado (`StatusVaga`), persiste, invalida cache e notifica via WebSocket — dentro da mesma transação/sessão |
| `redis_cache.py` | Cache de leitura de `/vagas` (get/set/invalidate), com _fail-open_: se o Redis estiver indisponível, loga aviso e segue sem cache (nunca derruba a requisição) |
| `ws_manager.py` | `ConnectionManager` in-memory (um `set` de `WebSocket`), broadcast best-effort (remove conexões mortas silenciosamente) |
| `whatsapp.py` | Cliente REST da Evolution API (`enviar_mensagem`) + parser de comandos do bot (`/vagas`, `/reservar`, `/cancelar`, `/status`, `/ajuda`) |
| `notificacoes.py` | Orquestra notificação multicanal de reservas (e-mail via Resend + WhatsApp), pulando o canal de origem quando a reserva já veio confirmada por ele |
| `email.py` / `email_templates.py` | Cliente Resend + templates HTML inline (confirmação, cancelamento, relatório diário) |
| `relatorios.py` (service) | Agregações SQL (contagem por status, entradas/saídas do dia, tempo médio de permanência, série histórica por dia) |

### 3.5 Entidades (modelos ORM) — ver seção 5 para o detalhamento completo de colunas/constraints.

### 3.6 Middlewares e segurança de borda

* **CORS** (`app/main.py:22-28`): `allow_origins=[settings.frontend_url]` — uma única origem exata, nunca `*`, com `allow_credentials=True` e métodos/headers explícitos.
* **TrustedHostMiddleware** (`app/main.py:30-31`): habilitado apenas quando `settings.is_production`, restringindo o `Host` header a `settings.api_host`.
* **Cabeçalhos de segurança** (`app/main.py:34-42`): middleware customizado adiciona `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, e `Strict-Transport-Security` (apenas em produção) em toda resposta.
* **Autenticação de rotas internas** (usadas por sistemas, não usuários): três padrões distintos de segredo compartilhado, todos retornando `404` (não `401`/`403`) quando o segredo é inválido, para não revelar a existência do endpoint:
  * `X-Cron-Secret` → `POST /reservas/expirar-vencidas`, `POST /relatorios/diario/enviar` (`app/config.py:55`, checado em `routers/reservas.py:92`, `routers/relatorios.py:43-44`).
  * `X-Internal-Secret` → `GET /admin/dominios/{d}/verificar`, `GET /admin/admins/{e}/verificar`, consumidos pela Auth0 Post-Login Action antes de existir um JWT de usuário (`routers/admin.py:22-25`).
  * Segredo embutido no **path** → `POST /webhook/whatsapp/{secret}` (`routers/webhook_whatsapp.py:15-22`).

---

## 4. Frontend

### 4.1 Framework e estrutura de pastas

Vite 6 + React 18 + TypeScript, com roteamento client-side (`react-router-dom` v7).

```text
frontend/src/
├── api/          # wrappers Axios tipados por recurso (vagas, reservas, movimentacoes, relatorios, admin, download)
├── auth/          # integração Auth0 (provider, guards de rota, token bridge, RBAC no cliente)
├── components/    # componentes de apresentação (Layout, VagaCard, EntradaModal, ReservaForm, charts/, ui/)
├── hooks/         # hooks de dados (TanStack Query) por recurso + WebSocket
├── lib/           # utilitários (queryClient singleton, cn(), tokens de cor dos gráficos)
├── offline/       # Dexie (IndexedDB): schema, fila de operações, sincronização
├── pages/         # telas roteadas: Login, Home, Reservas, Relatorios, Admin
├── stores/        # estado de UI local (Zustand)
├── App.tsx        # tabela de rotas + guards
└── main.tsx        # composição de providers (Router > Auth0 > QueryClient > App)
```

### 4.2 Fluxo de navegação

```text
/login        → pública, botão "Entrar com Google" (Auth0 loginWithRedirect)
/             → Home (protegida) — grade de vagas do andar selecionado
/reservas     → protegida — formulário de nova reserva + lista de reservas
/relatorios   → protegida + RequireAdmin — dashboard analítico + export PDF/CSV
/admin        → protegida + RequireAdmin — domínios autorizados, admins, audit log
```

`App.tsx:35-61` define essa tabela. Toda rota (exceto `/login`) passa por `withAuthenticationRequired`
(Auth0 SDK) via `withProtection`; `/relatorios` e `/admin` adicionalmente passam por `RequireAdmin`,
que lê o claim customizado `https://estacionamento.dom/role` do objeto `user` do Auth0 (não uma
chamada de rede — a checagem de admin no frontend é apenas para roteamento/UX; a autorização real é
sempre revalidada no backend via `require_role("admin")` em cada rota administrativa).

### 4.3 Gerenciamento de estado — três mecanismos, cada um com um papel distinto

| Mecanismo | Escopo | Persiste? | Exemplo |
|---|---|---|---|
| **Zustand** (`useUiStore`) | Estado de UI efêmero, síncrono | Não | Andar selecionado no dashboard |
| **TanStack Query** | Estado de servidor (cache + invalidação) | Em memória (não sobrevive a reload) | `useVagas`, `useReservas`, `useRelatorioDiario`, `useHistorico`, `useDominios`, `useAdmins`, `useAuditLogs` |
| **Dexie / IndexedDB** | Estado offline durável | Sim, no navegador | Fila `operacoes` (mutações pendentes) + `vagasCache` (última leitura conhecida por andar) |

### 4.4 Comunicação com a API

Uma única instância Axios (`api/client.ts`) com um interceptor de request que injeta
`Authorization: Bearer <token>`. O *getter* do token é plugado uma única vez, perto da raiz do app,
por `useApiToken()` (`auth/useApiToken.ts`), que embrulha `getAccessTokenSilently` do Auth0. Isso
desacopla os módulos de `api/*.ts` de qualquer dependência direta do SDK do Auth0.

O WebSocket (`hooks/useVagasSocket.ts`) é a **exceção**: como o navegador não permite cabeçalhos
customizados no handshake de WebSocket, o JWT é passado como **query string**
(`/ws/vagas?token=...`), validado pelo backend com a mesma função `decode_token()` usada nas rotas
REST (`routers/ws.py:15-19`).

### 4.5 Fluxo de dados offline-first (funcionalidade central do produto)

```plantuml
@startuml Fluxo_Offline
!pragma layout smetana
title Fluxo offline-first — executarOuEnfileirar()

start
:Usuário aciona uma mutação\n(ocupar vaga / liberar / reservar / cancelar);
if (navigator.onLine == false?) then (sim)
  :Serializa operação em db.operacoes (Dexie);
  :Aplica patch otimista no cache\nTanStack Query + Dexie.vagasCache;
  :Retorna {enfileirada: true} para a UI;
else (não)
  :Executa chamada Axios real;
  if (falhou por erro de rede\n(sem error.response)?) then (sim)
    :Serializa operação em db.operacoes (Dexie);
    :Aplica patch otimista;
  else (não — sucesso ou erro de negócio)
    :Invalida queries ['vagas']/['reservas'];
    :Propaga resultado/erro normalmente;
  endif
endif
stop
@enduml
```

Quando o navegador dispara o evento `online` (ou ao montar o app já online), `sincronizarPendentes()`
(`offline/sync.ts:27-62`) envia **todo o lote pendente em uma única chamada** para
`POST /movimentacoes/sync`. O backend processa cada item independentemente (ver seção 8.7 — fluxo de
tratamento de exceções); a resposta traz um resultado por item, e o cliente remove da fila apenas os
que tiveram sucesso, incrementando `tentativas` e guardando a mensagem de erro dos que falharam (para
retry manual via o botão "Sincronizar agora" em `StatusConexao.tsx`).

### 4.6 Componentes — responsabilidade de cada um

| Componente | Responsabilidade |
|---|---|
| `Layout` | Casca visual (cabeçalho, navegação condicionada por `useIsAdmin`, logout, `StatusConexao`) |
| `VagaCard` | Card de uma vaga: status, ocupante/reserva atual, ação (ocupar/liberar) conforme `status` |
| `EntradaModal` | Formulário modal de registro de entrada (nome, placa, veículo, tipo de cliente, observações) |
| `ReservaForm` | Formulário de nova reserva, com `<select>` de vagas livres |
| `StatusConexao` | Indicador online/offline + contagem de operações pendentes no Dexie (`useLiveQuery`) + botão de sync manual |
| `StatTile` | Tile numérico simples (KPI) usado no dashboard de relatórios |
| `charts/StatusVagasChart` | Gráfico de barras horizontal (Recharts) — contagem de vagas por status |
| `charts/HistoricoChart` | Gráfico de linha (Recharts) — entradas/saídas por dia |
| `components/ui/*` | Primitivos shadcn/ui (`Button`, `Input`, `Label`, `Select`, `Dialog`, `Badge`) sobre Radix + CVA |

### 4.7 PWA

`vite-plugin-pwa` gera manifest (nome, ícones 192/512px, tema escuro) e service worker via Workbox
(`vite.config.ts:9-37`), com `registerType: 'autoUpdate'` e uma regra de cache em runtime
(`NetworkFirst` para requisições cujo host bate com o regex `/^https:\/\/api\./`). Ver observação
sobre esse regex na seção de limitações.

---

## 5. Banco de dados

### 5.1 Tabelas

Todas as 7 tabelas usam **tipos genéricos do SQLAlchemy** (`String`, `Integer`, `Boolean`, `DateTime`,
`Text`, `Enum`) — nenhum tipo dialect-specific foi encontrado em nenhum modelo, confirmando a regra
de compatibilidade MySQL↔PostgreSQL do `PROJECT_SPEC.md` como efetivamente seguida no código.

| Tabela | PK | FKs | Colunas notáveis | Observação |
|---|---|---|---|---|
| `vagas` | `id` (String(20), chave natural, ex. `"S2-49"`) | — | `status` (enum `status_vaga`: livre/ocupada/reservada/manutencao), `ativo` (bool) | `ativo=false` é **soft-delete** — `DELETE /vagas/{id}` nunca remove a linha |
| `ocupantes` | `id` (Integer, autoincrement) | `vaga_id → vagas.id` | `tipo_cliente` (enum), `hora_entrada`, `operador_id` (string livre — `sub` do Auth0) | Ver nota de integridade abaixo |
| `reservas` | `id` (Integer, autoincrement) | `vaga_id → vagas.id` | `status` (String livre: `ativa`/`concluida`/`cancelada`/`expirada`), `canal` (`webapp`/`whatsapp`) | `status` não é um `Enum` de banco, é convenção de aplicação |
| `movimentacoes` | `id` (Integer, autoincrement) | `vaga_id → vagas.id` | `tipo` (`entrada`/`saida`), `tempo_permanencia_min` (nullable), `sincronizado` (bool, default true) | Ver nota sobre `sincronizado` abaixo |
| `audit_logs` | `id` (Integer, autoincrement) | — (nenhuma FK; `usuario_id` é string livre) | `detalhes` (Text, JSON serializado manualmente via `json.dumps`) | Ver nota de cobertura de auditoria abaixo |
| `dominios_autorizados` | `dominio` (String, chave natural) | — | `ativo` (bool) | Consultada pela Auth0 Post-Login Action |
| `admin_emails` | `email` (String, chave natural) | — | — | Consultada pela Auth0 Post-Login Action |

Não existe uma tabela local de usuários/contas — a identidade é inteiramente delegada ao Auth0; o
backend nunca persiste um "usuário", apenas referências textuais ao `sub` (ou ao e-mail, nas listas de
autorização).

### 5.2 Diagrama Entidade-Relacionamento

```plantuml
@startuml ER_Banco_de_Dados
!pragma layout smetana
title Modelo de dados — Estacionamento Dom Pagamentos

entity "vagas" as vagas {
  * id : VARCHAR(20) <<PK>>
  --
  numero : VARCHAR(10)
  andar : VARCHAR(5)
  posicao : VARCHAR(50) <<null>>
  tipo : VARCHAR(20) = 'normal'
  status : ENUM(livre,ocupada,reservada,manutencao) = livre
  ativo : BOOLEAN = true
  criado_em : DATETIME
}

entity "ocupantes" as ocupantes {
  * id : INTEGER <<PK, autoincrement>>
  --
  # vaga_id : VARCHAR(20) <<FK>>
  nome : VARCHAR(100)
  placa : VARCHAR(10)
  veiculo : VARCHAR(100)
  tipo_cliente : ENUM(mensalista,rotativo,visitante,prestador)
  hora_entrada : DATETIME
  observacoes : TEXT <<null>>
  operador_id : VARCHAR(200)
}

entity "reservas" as reservas {
  * id : INTEGER <<PK, autoincrement>>
  --
  # vaga_id : VARCHAR(20) <<FK>>
  nome : VARCHAR(100)
  telefone : VARCHAR(20) <<null>>
  email : VARCHAR(100) <<null>>
  placa : VARCHAR(10) <<null>>
  inicio : DATETIME
  fim : DATETIME
  status : VARCHAR(20) = 'ativa'
  canal : VARCHAR(20) = 'webapp'
  criado_em : DATETIME
}

entity "movimentacoes" as movimentacoes {
  * id : INTEGER <<PK, autoincrement>>
  --
  # vaga_id : VARCHAR(20) <<FK>>
  tipo : VARCHAR(20)
  placa : VARCHAR(10)
  motorista : VARCHAR(100)
  veiculo : VARCHAR(100)
  timestamp : DATETIME
  operador_id : VARCHAR(200)
  tempo_permanencia_min : INTEGER <<null>>
  sincronizado : BOOLEAN = true
}

entity "audit_logs" as audit_logs {
  * id : INTEGER <<PK, autoincrement>>
  --
  usuario_id : VARCHAR(200)
  acao : VARCHAR(100)
  recurso : VARCHAR(50)
  recurso_id : VARCHAR(50) <<null>>
  ip : VARCHAR(45) <<null>>
  timestamp : DATETIME
  detalhes : TEXT <<null, JSON serializado>>
}

entity "dominios_autorizados" as dominios {
  * dominio : VARCHAR(255) <<PK>>
  --
  ativo : BOOLEAN = true
  criado_em : DATETIME
}

entity "admin_emails" as admins {
  * email : VARCHAR(255) <<PK>>
  --
  criado_em : DATETIME
}

vagas ||--o{ ocupantes : "1..N (intenção: 0..1 ativo\nsem constraint no banco)"
vagas ||--o{ reservas   : "1..N"
vagas ||--o{ movimentacoes : "1..N"

note bottom of ocupantes
  Não há UNIQUE/constraint em vaga_id.
  O invariante "no máximo 1 ocupante ativo
  por vaga" é garantido apenas pela
  regra de negócio em services/sync.py
  (checagem de Vaga.status antes do INSERT).
end note

note right of audit_logs
  Sem FK para nenhuma tabela — usuario_id
  é texto livre (sub do Auth0 ou
  "whatsapp:<telefone>"). Não é alimentada
  pelas rotas de admin.py (CRUD de
  domínios/admins não é auditado).
end note
@enduml
```

### 5.3 Migrações (Alembic)

```plantuml
@startuml Fluxo_Migracoes
!pragma layout smetana
title Fluxo de migrações — Alembic

(*) --> "0001_initial\n(vagas, ocupantes, reservas,\nmovimentacoes, audit_logs)"
--> "0002_admin_dominios\n(dominios_autorizados, admin_emails)"
--> (*)

note right
  alembic/env.py importa todos os
  módulos de app.models para registrar
  metadados em Base.metadata antes de
  comparar/gerar migrações.

  Em produção, "alembic upgrade head"
  roda automaticamente no CMD do
  container (backend/Dockerfile:42),
  antes do gunicorn subir — toda
  inicialização de container aplica
  migrações pendentes.
end note
@enduml
```

### 5.4 Representação ORM

SQLAlchemy 2.0 estilo declarativo (`Mapped[T]` + `mapped_column(...)`), uma classe por tabela, todas
herdando de `Base(DeclarativeBase)` (`app/models/base.py`). Enums Python (`StatusVaga`, `TipoCliente`)
são declarados nos próprios módulos de modelo e mapeados via `sqlalchemy.Enum(..., name=...)` —
portáveis entre MySQL e PostgreSQL porque o SQLAlchemy emula o tipo quando o dialeto não o suporta
nativamente (MySQL não tem `ENUM` nomeado como PostgreSQL, mas o SQLAlchemy compensa isso).

---

## 6. Infraestrutura e deploy

### 6.1 Desenvolvimento local

`docker-compose.yml` (raiz) sobe 4 serviços: `mysql:8.0` (com healthcheck), `redis:7-alpine`
(protegido por senha), `backend` (build local, `--reload`, volume bind-mount do código) e `frontend`
(build local, servido por nginx na porta 3000). Um `docker-compose.yml` **separado** em
`evolution-api/` sobe uma instância local da Evolution API + Postgres + Redis próprios, para testes
de integração do WhatsApp — o próprio arquivo documenta que não é para produção
(`evolution-api/docker-compose.yml:3-4`).

### 6.2 Build

* **Backend**: `Dockerfile` multi-stage — estágio `builder` (`python:3.12-slim` + `build-essential`
  + `libffi-dev`) compila um virtualenv (`/opt/venv`) a partir de `requirements.txt`; estágio final
  copia apenas o venv + as bibliotecas nativas de runtime do weasyprint (`libpango`, `libpangocairo`,
  `libgdk-pixbuf`, `libcairo2`, `fonts-liberation`) + `curl` (para o `HEALTHCHECK`), roda como usuário
  não-root `appuser` (uid 1000).
* **Frontend**: `Dockerfile` multi-stage — `node:20-alpine` roda `npm ci && npm run build`
  (build args `VITE_API_URL`/`VITE_AUTH0_DOMAIN`/`VITE_AUTH0_CLIENT_ID`/`VITE_AUTH0_AUDIENCE` — essas
  variáveis são **compiladas estaticamente no bundle**, portanto uma mudança exige rebuild, não
  apenas restart); o resultado (`dist/`) é servido por `nginx:alpine` com fallback de SPA
  (`try_files ... /index.html`) e cache imutável de 1 ano para `/assets/`.

### 6.3 Processo de migração do banco

A migração **não é um passo manual de deploy** — é parte do `CMD` do container backend:
```
alembic upgrade head && gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --workers 4 --bind 0.0.0.0:${PORT:-8000}
```
Ou seja, toda vez que o container backend inicia (deploy novo ou restart), migrações pendentes são
aplicadas **antes** do servidor HTTP começar a aceitar tráfego (`backend/Dockerfile:42-44`).

### 6.4 Inicialização da aplicação e execução em produção

```plantuml
@startuml Atividade_Inicializacao
!pragma layout smetana
title Atividade — inicialização do container backend em produção (Railway)

start
:Railway inicia o container a partir\nda imagem construída pelo Dockerfile;
:CMD executa "alembic upgrade head";
if (migração falhou?) then (sim)
  :Container encerra com erro;
  :Railway aplica restartPolicy\n(ON_FAILURE, até 3 tentativas);
  stop
else (não)
  :Gunicorn sobe 4 workers\nUvicornWorker, bind 0.0.0.0:$PORT;
  :FastAPI registra middlewares\n(CORS, TrustedHost, security headers);
  :FastAPI registra routers\n(vagas, reservas, movimentacoes,\nrelatorios, admin, webhook, ws);
  :Railway começa a chamar\nGET /health periodicamente;
  if (DB e Redis respondem?) then (sim)
    :/health retorna 200 {"status":"ok"};
    :Serviço considerado saudável;
  else (não)
    :/health retorna 503 {"status":"degradado"};
    :Railway reinicia o container\n(restartPolicy ON_FAILURE);
  endif
endif
stop
@enduml
```

Não há nenhuma tarefa em background/scheduler embutida no processo Python — os dois "cron jobs" do
sistema (expirar reservas vencidas, disparar relatório diário) são **endpoints HTTP comuns**
acionados por um agendador externo (Railway Cron Job fazendo `curl` com o header `X-Cron-Secret`).
O backend, por si só, não tem noção de tempo agendado.

### 6.5 Topologia de deploy (Railway)

Ver diagrama de implantação completo na seção 7.6. Resumo textual:

* **3 serviços a partir deste repositório**: `backend` (root dir `backend`), `frontend` (root dir
  `frontend`), ambos com builder Dockerfile + healthcheck (`/health` e `/`, respectivamente) e
  `restartPolicyType = ON_FAILURE` (`backend/railway.toml`, `frontend/railway.toml`).
* **Evolution API**: deployada a partir do **template oficial do Railway** (não deste repositório),
  com um Postgres e um Redis próprios, e um **Volume Railway persistente** montado em
  `/evolution/instances` — sem isso, a sessão do WhatsApp (QR code escaneado) é perdida a cada
  redeploy (`DEPLOY.md:92-97`).
* **2 plugins gerenciados do Railway** usados pelo `backend`: PostgreSQL e Redis (referenciados via
  `${{Postgres.DATABASE_URL}}` / `${{Redis.REDIS_URL}}`).
* **Normalização de `DATABASE_URL`** (`app/config.py:17-30`): aceita a URL crua do plugin Railway
  (`postgres://` ou `postgresql://`, sem driver assíncrono) e a reescreve para
  `postgresql+asyncpg://` (ou `mysql://` → `mysql+aiomysql://`) — mecanismo que permite colar a
  variável do Railway sem edição manual.
* **Variáveis de ambiente** (ver lista completa em `.env.example`): banco, Redis, ambiente/porta,
  Auth0, Evolution API, Resend, `CRON_SECRET`, `AUTH0_ACTION_SECRET`, e as `VITE_*` (build-time, só
  no frontend).
* **Bootstrap obrigatório e único**: nada consegue logar até existir ao menos uma linha em
  `dominios_autorizados` (e tipicamente em `admin_emails`) — `scripts/seed_admin.py`, rodado uma vez
  via `railway run --service backend python -m scripts.seed_admin --dominio ... --admin ...`
  (`DEPLOY.md:70-77`). Depois disso, o próprio painel `/admin` gerencia o resto.

### 6.6 CI/CD

`.github/workflows/ci.yml` roda em push/PR para `main`, com dois jobs paralelos:

* `backend-tests`: instala as libs nativas do weasyprint, `pip install -r requirements.txt`, `pytest -q`.
* `frontend-build`: `npm ci`, `npm run build` (que roda `tsc -b && vite build` — ou seja, também
  valida os tipos TypeScript).

**Não há job de deploy (CD) neste workflow.** O `DEPLOY.md` é explícito: o deploy real depende de
conectar o repositório no dashboard do Railway (ação manual, feita uma vez, fora do controle de
versão) — cada push em `main` então dispara um build/deploy automático do lado do Railway, mas isso
não está codificado como um step de Actions neste repositório.

---

## 7. Diagramas UML obrigatórios

### 7.1 Diagrama de Componentes

```plantuml
@startuml Componentes
!pragma layout smetana
skinparam componentStyle rectangle
title Diagrama de Componentes

package "Frontend (SPA)" {
  [App / Router] as App
  [Auth (Auth0 bridge + guards)] as Auth
  [API Client (Axios)] as ApiClient
  [Hooks (TanStack Query)] as Hooks
  [Offline (Dexie)] as Offline
  [Componentes de UI] as UI
}

package "Backend (FastAPI)" {
  [Routers] as Routers
  [Security (JWT/RBAC/Audit)] as Security
  [Services] as Services
  [Modelos ORM] as Models
  [WS Manager] as WS
}

database "Banco relacional\n(MySQL/PostgreSQL)" as DB
database "Redis" as Redis

component "Auth0" as Auth0Ext
component "Evolution API" as EvoExt
component "Resend" as ResendExt
component "Railway Cron" as CronExt

UI --> Hooks
Hooks --> ApiClient
Hooks --> Offline
App --> Auth
Auth --> ApiClient : injeta JWT
ApiClient --> Routers : REST
App ..> WS : WebSocket

Routers --> Security
Routers --> Services
Services --> Models
Models --> DB
Services --> Redis
Routers --> Redis : leitura de cache

Security ..> Auth0Ext : valida JWT (JWKS)
Auth ..> Auth0Ext : login
Auth0Ext ..> Routers : Post-Login Action\n(/admin/*/verificar)

Services ..> EvoExt : envia mensagens
EvoExt ..> Routers : webhook
Services ..> ResendExt : envia e-mails
CronExt ..> Routers : dispara tarefas agendadas
@enduml
```

### 7.2 Diagrama de Classes

```plantuml
@startuml Classes
!pragma layout smetana
title Diagrama de Classes — Domínio e Persistência

enum StatusVaga {
  livre
  ocupada
  reservada
  manutencao
}

enum TipoCliente {
  mensalista
  rotativo
  visitante
  prestador
}

class Vaga {
  +id : str  <<PK>>
  +numero : str
  +andar : str
  +posicao : str?
  +tipo : str = "normal"
  +status : StatusVaga = livre
  +ativo : bool = true
  +criado_em : datetime
}

class Ocupante {
  +id : int  <<PK>>
  +vaga_id : str  <<FK>>
  +nome : str
  +placa : str
  +veiculo : str
  +tipo_cliente : TipoCliente
  +hora_entrada : datetime
  +observacoes : str?
  +operador_id : str
}

class Reserva {
  +id : int  <<PK>>
  +vaga_id : str  <<FK>>
  +nome : str
  +telefone : str?
  +email : str?
  +placa : str?
  +inicio : datetime
  +fim : datetime
  +status : str = "ativa"
  +canal : str = "webapp"
  +criado_em : datetime
}

class Movimentacao {
  +id : int  <<PK>>
  +vaga_id : str  <<FK>>
  +tipo : str
  +placa : str
  +motorista : str
  +veiculo : str
  +timestamp : datetime
  +operador_id : str
  +tempo_permanencia_min : int?
  +sincronizado : bool = true
}

class AuditLog {
  +id : int  <<PK>>
  +usuario_id : str
  +acao : str
  +recurso : str
  +recurso_id : str?
  +ip : str?
  +timestamp : datetime
  +detalhes : str?  <<JSON serializado>>
}

class DominioAutorizado {
  +dominio : str  <<PK>>
  +ativo : bool = true
  +criado_em : datetime
}

class AdminEmail {
  +email : str  <<PK>>
  +criado_em : datetime
}

Vaga "1" *-- "0..N" Ocupante : vaga_id
Vaga "1" *-- "0..N" Reserva : vaga_id
Vaga "1" *-- "0..N" Movimentacao : vaga_id
Vaga ..> StatusVaga
Ocupante ..> TipoCliente

class "sync (module)" as SyncService <<service>> {
  +aplicar_entrada(db, payload, operador_sub) : Movimentacao
  +aplicar_saida(db, vaga_id, operador_sub) : Movimentacao
  +aplicar_reserva(db, payload, operador_sub) : Reserva
  +aplicar_cancelamento(db, reserva_id, operador_sub) : Reserva
  +expirar_reservas_vencidas(db) : list<Reserva>
}
class "RecursoNaoEncontradoError" as ErroNaoEncontrado <<exception>>
class "ConflitoOperacaoError" as ErroConflito <<exception>>
SyncService ..> ErroNaoEncontrado
SyncService ..> ErroConflito
SyncService --> Vaga
SyncService --> Ocupante
SyncService --> Reserva
SyncService --> Movimentacao

class "VagaComDetalhes" as VagaDTO <<DTO/schema>> {
  +id : str
  +status : StatusVaga
  +ocupante : OcupanteRead?
  +reserva_ativa : ReservaRead?
}
VagaDTO ..> Vaga : model_validate
@enduml
```

*Nota de fidelidade:* `SyncService` representa o módulo `app/services/sync.py`, que no código é um
conjunto de funções de módulo (não uma classe Python). A notação de classe com métodos "estáticos" é
usada aqui apenas como convenção de representação UML — não existe uma classe `Sync`/`SyncService`
literal no código.

### 7.3 Diagrama de Pacotes

```plantuml
@startuml Pacotes
!pragma layout smetana
title Diagrama de Pacotes

package "backend.app" {
  package "routers" as pkg_routers
  package "services" as pkg_services
  package "security" as pkg_security
  package "schemas" as pkg_schemas
  package "models" as pkg_models
  package "main/config/database" as pkg_core
}

pkg_routers ..> pkg_services
pkg_routers ..> pkg_security
pkg_routers ..> pkg_schemas
pkg_routers ..> pkg_models : leituras diretas (select/get)
pkg_services ..> pkg_models
pkg_services ..> pkg_schemas
pkg_security ..> pkg_models
pkg_core ..> pkg_routers : registra

package "frontend.src" {
  package "pages" as pkg_pages
  package "components" as pkg_components
  package "hooks" as pkg_hooks
  package "api" as pkg_api
  package "auth" as pkg_auth
  package "offline" as pkg_offline
  package "stores" as pkg_stores
  package "lib" as pkg_lib
}

pkg_pages ..> pkg_components
pkg_pages ..> pkg_hooks
pkg_pages ..> pkg_stores
pkg_components ..> pkg_hooks
pkg_components ..> pkg_auth
pkg_hooks ..> pkg_api
pkg_hooks ..> pkg_offline
pkg_api ..> pkg_auth : token via interceptor
pkg_offline ..> pkg_api
pkg_components ..> pkg_lib

pkg_api ..> pkg_routers : HTTP/REST
@enduml
```

### 7.4 Diagrama de Casos de Uso

```plantuml
@startuml Casos_de_Uso
!pragma layout smetana
left to right direction
title Diagrama de Casos de Uso

actor Operador
actor Administrador
actor "Cliente (WhatsApp)" as ClienteWA
actor "Agendador externo\n(Railway Cron)" as Cron
actor "Auth0 Post-Login Action" as Auth0Action

Administrador --|> Operador

rectangle "Sistema de Estacionamento" {
  usecase "Fazer login (Google/Auth0)" as UC_Login
  usecase "Consultar vagas" as UC_ConsultarVagas
  usecase "Registrar entrada de veículo" as UC_Entrada
  usecase "Registrar saída de veículo" as UC_Saida
  usecase "Criar reserva" as UC_CriarReserva
  usecase "Cancelar reserva" as UC_CancelarReserva
  usecase "Sincronizar operações offline" as UC_Sync
  usecase "Cadastrar/editar/desativar vaga" as UC_CRUDVaga
  usecase "Ver relatório diário e histórico" as UC_Relatorios
  usecase "Exportar PDF/CSV" as UC_Export
  usecase "Gerenciar domínios autorizados" as UC_Dominios
  usecase "Gerenciar e-mails admin" as UC_Admins
  usecase "Ver log de auditoria" as UC_AuditLog
  usecase "Consultar vagas via WhatsApp" as UC_WA_Consulta
  usecase "Reservar via WhatsApp" as UC_WA_Reservar
  usecase "Cancelar via WhatsApp" as UC_WA_Cancelar
  usecase "Expirar reservas vencidas" as UC_Expirar
  usecase "Disparar relatório diário por e-mail" as UC_DispararRelatorio
  usecase "Verificar domínio/admin\n(bootstrap de login)" as UC_Verificar
}

Operador --> UC_Login
Operador --> UC_ConsultarVagas
Operador --> UC_Entrada
Operador --> UC_Saida
Operador --> UC_CriarReserva
Operador --> UC_CancelarReserva
UC_Entrada ..> UC_Sync : <<include>>\n(quando offline)
UC_Saida ..> UC_Sync : <<include>>\n(quando offline)

Administrador --> UC_CRUDVaga
Administrador --> UC_Relatorios
Administrador --> UC_Export
Administrador --> UC_Dominios
Administrador --> UC_Admins
Administrador --> UC_AuditLog

ClienteWA --> UC_WA_Consulta
ClienteWA --> UC_WA_Reservar
ClienteWA --> UC_WA_Cancelar

Cron --> UC_Expirar
Cron --> UC_DispararRelatorio
Auth0Action --> UC_Verificar
UC_Login ..> UC_Verificar : <<include>>
@enduml
```

### 7.5 Diagrama de Atividades — ver seção 8 (tratamento de exceções e inicialização), e seção 4.5
(fluxo offline).

### 7.6 Diagrama de Implantação (Deployment)

```plantuml
@startuml Implantacao
!pragma layout smetana
title Diagrama de Implantação — Produção (Railway)

node "Navegador do usuário" as Browser {
  artifact "SPA (React)\n+ Service Worker" as SPA
  database "IndexedDB\n(Dexie)" as IDB
}

cloud "Railway (projeto)" {
  node "Serviço: frontend\n(container nginx:alpine)" as NodeFrontend {
    artifact "dist/ (build Vite)" as DistArtifact
  }

  node "Serviço: backend\n(container python:3.12-slim)" as NodeBackend {
    artifact "gunicorn + 4x UvicornWorker\napp.main:app" as BackendArtifact
  }

  node "Serviço: Evolution API\n(template Railway)" as NodeEvolution {
    artifact "atendai/evolution-api" as EvoArtifact
    storage "Volume: /evolution/instances\n(sessão WhatsApp persistente)" as EvoVolume
  }

  database "Plugin PostgreSQL" as PGPlugin
  database "Plugin Redis" as RedisPlugin
  database "Postgres próprio\n(Evolution)" as EvoPG
  database "Redis próprio\n(Evolution)" as EvoRedis

  node "Railway Cron Job" as CronJob
}

cloud "Auth0 (tenant)" as Auth0Cloud
cloud "Resend" as ResendCloud
cloud "WhatsApp (rede Meta)" as WhatsAppNet

Browser --> NodeFrontend : HTTPS (carrega SPA)
SPA --> NodeBackend : HTTPS REST + WSS\n(Bearer JWT)
SPA <--> IDB : leitura/escrita offline

NodeBackend --> PGPlugin : asyncpg (SQL)
NodeBackend --> RedisPlugin : cache /vagas
NodeBackend ..> Auth0Cloud : validação JWT (JWKS)
NodeBackend ..> ResendCloud : envio de e-mail
NodeBackend <..> NodeEvolution : webhook + REST\n(WHATSAPP_WEBHOOK_SECRET)
NodeEvolution --> EvoVolume
NodeEvolution --> EvoPG
NodeEvolution --> EvoRedis
NodeEvolution <--> WhatsAppNet

CronJob --> NodeBackend : POST /reservas/expirar-vencidas\nPOST /relatorios/diario/enviar\n(X-Cron-Secret)

SPA ..> Auth0Cloud : Universal Login (redirect)
@enduml
```

---

## 8. Diagramas de fluxo de dados

### 8.1 Fluxo completo de requisição (consulta de vagas, ilustra cache)

```plantuml
@startuml Seq_Fluxo_Completo
title Sequência — GET /vagas (fluxo completo: usuário → resposta)

actor Usuário
participant "SPA (Home.tsx)" as SPA
participant "useVagas (hook)" as Hook
participant "Axios (api/client.ts)" as Axios
participant "Router /vagas" as Controller
participant "redis_cache" as Cache
participant "_montar_vagas_com_detalhes" as ServiceFn
participant "AsyncSession (ORM)" as ORM
database "Banco (Postgres/MySQL)" as DB
database "Redis" as Redis

Usuário -> SPA : abre Home / troca de andar
SPA -> Hook : useVagas(andar)
Hook -> Axios : GET /vagas?andar=S2
Axios -> Controller : HTTP + Authorization: Bearer <JWT>
Controller -> Controller : Depends(get_current_user)\n valida JWT (JWKS Auth0)
Controller -> Cache : get_vagas_cache(andar)
Cache -> Redis : GET vagas:list:S2

alt cache HIT
  Redis --> Cache : JSON
  Cache --> Controller : payload em cache
  Controller --> Axios : 200 (lista de VagaComDetalhes)
else cache MISS
  Redis --> Cache : nil
  Controller -> ServiceFn : monta detalhes
  ServiceFn -> ORM : select(Vaga), select(Ocupante), select(Reserva ativa)
  ORM -> DB : SQL
  DB --> ORM : linhas
  ORM --> ServiceFn : entidades
  ServiceFn --> Controller : list[VagaComDetalhes]
  Controller -> Cache : set_vagas_cache(andar, json)
  Cache -> Redis : SET ... EX 30
  Controller --> Axios : 200 (lista de VagaComDetalhes)
end

Axios --> Hook : dados
Hook -> Hook : grava em db.vagasCache (Dexie)\n(fallback para próxima falha de rede)
Hook --> SPA : renderiza VagaCard[]
@enduml
```

### 8.2 Fluxo de autenticação

```plantuml
@startuml Seq_Autenticacao
title Sequência — Login e validação de JWT

actor Usuário
participant "SPA" as SPA
participant "Auth0 Universal Login" as Auth0UL
participant "Post-Login Action" as Action
participant "Backend /admin/*/verificar" as AdminAPI
database "dominios_autorizados\n/ admin_emails" as DB
participant "Backend (rota protegida)" as API

Usuário -> SPA : clica "Entrar com Google"
SPA -> Auth0UL : loginWithRedirect()
Auth0UL -> Usuário : tela de login Google
Usuário -> Auth0UL : autentica com Google

Auth0UL -> Action : onExecutePostLogin(event)
Action -> AdminAPI : GET /dominios/{dominio}/verificar\n(header X-Internal-Secret)
AdminAPI -> DB : SELECT dominio, ativo
DB --> AdminAPI : registro ou nulo
AdminAPI --> Action : {"autorizado": bool}

alt domínio não autorizado
  Action -> Auth0UL : api.access.deny(...)
  Auth0UL --> SPA : erro de acesso negado
else domínio autorizado
  Action -> AdminAPI : GET /admins/{email}/verificar\n(header X-Internal-Secret)
  AdminAPI -> DB : SELECT email
  DB --> AdminAPI : registro ou nulo
  AdminAPI --> Action : {"admin": bool}
  Action -> Action : idToken.setCustomClaim(\n"https://estacionamento.dom/role",\nadmin ? "admin" : "operador")
  Action -> Auth0UL : continua login
  Auth0UL --> SPA : redirect com JWT (RS256)\n+ id_token com claim de role
end

SPA -> API : requisição REST com\nAuthorization: Bearer <JWT>
API -> API : PyJWKClient busca chave pública\n(JWKS do tenant Auth0)
API -> API : jwt.decode(RS256, audience, issuer)

alt token inválido/expirado
  API --> SPA : 401
else token válido
  API -> API : require_role(...) checa claim de role
  API --> SPA : 200 (ou 403 se role insuficiente)
end
@enduml
```

### 8.3 Fluxo de criação — registrar entrada de veículo

```plantuml
@startuml Seq_Criacao_Entrada
title Sequência — POST /movimentacoes/entrada (criação)

actor Operador
participant "EntradaModal" as UI
participant "useOcuparVaga" as Hook
participant "executarOuEnfileirar" as Offline
participant "Router /movimentacoes" as Controller
participant "aplicar_entrada (sync.py)" as UseCase
participant "AsyncSession" as ORM
database "Banco" as DB
participant "redis_cache" as Cache
participant "ws_manager" as WS
participant "audit.py" as Audit

Operador -> UI : preenche nome/placa/veículo/tipo
UI -> Hook : mutate(EntradaPayload)
Hook -> Offline : executarOuEnfileirar(chamada, operacao)

alt offline ou falha de rede
  Offline --> Hook : {enfileirada: true}
  Hook -> Hook : patch otimista no cache\n(status=ocupada)
else online
  Offline -> Controller : POST /movimentacoes/entrada
  Controller -> UseCase : aplicar_entrada(db, payload, sub)
  UseCase -> ORM : get(Vaga, vaga_id)
  ORM -> DB : SELECT
  DB --> ORM : Vaga

  alt vaga inexistente/inativa
    UseCase --> Controller : raise RecursoNaoEncontradoError
    Controller --> Offline : 404
  else vaga não disponível (status != livre/reservada)
    UseCase --> Controller : raise ConflitoOperacaoError
    Controller --> Offline : 409
  else vaga disponível
    UseCase -> ORM : add(Ocupante)
    UseCase -> ORM : (se reservada) marca reservas ativas\ncomo "concluida"
    UseCase -> ORM : vaga.status = ocupada
    UseCase -> ORM : add(Movimentacao tipo=entrada)
    UseCase -> DB : COMMIT
    UseCase -> Cache : invalidate_vagas_cache()
    UseCase -> WS : broadcast {vaga_atualizada}
    UseCase --> Controller : Movimentacao
    Controller -> Audit : registrar_auditoria(entrada)
    Audit -> DB : INSERT audit_logs
    Controller --> Offline : 201 Movimentacao
  end
  Offline --> Hook : resultado
  Hook -> Hook : invalidate ['vagas']
end
Hook --> UI : sucesso/erro
@enduml
```

### 8.4 Fluxo de atualização — editar vaga (admin)

```plantuml
@startuml Seq_Atualizacao
title Sequência — PATCH /vagas/{vaga_id} (atualização)

actor Administrador
participant "Painel Admin (frontend)" as UI
participant "Router /vagas" as Controller
participant "AsyncSession" as ORM
database "Banco" as DB
participant "redis_cache" as Cache
participant "audit.py" as Audit

Administrador -> UI : edita campos da vaga
UI -> Controller : PATCH /vagas/{id}\n(VagaUpdate, Bearer JWT admin)
Controller -> Controller : Depends(require_role("admin"))
Controller -> ORM : get(Vaga, vaga_id)
ORM -> DB : SELECT

alt vaga não encontrada
  Controller --> UI : 404
else vaga encontrada
  Controller -> ORM : setattr(vaga, campo, valor)\npara cada campo em exclude_unset
  Controller -> DB : COMMIT
  Controller -> Cache : invalidate_vagas_cache()
  Controller -> Audit : registrar_auditoria("atualizar_vaga")
  Audit -> DB : INSERT audit_logs
  Controller --> UI : 200 VagaRead
end
@enduml
```

### 8.5 Fluxo de exclusão — desativar vaga (soft delete)

```plantuml
@startuml Seq_Exclusao
title Sequência — DELETE /vagas/{vaga_id} (exclusão lógica)

actor Administrador
participant "Painel Admin" as UI
participant "Router /vagas" as Controller
participant "AsyncSession" as ORM
database "Banco" as DB
participant "redis_cache" as Cache
participant "audit.py" as Audit

Administrador -> UI : clica "remover vaga"
UI -> Controller : DELETE /vagas/{id}\n(Bearer JWT admin)
Controller -> Controller : Depends(require_role("admin"))
Controller -> ORM : get(Vaga, vaga_id)
ORM -> DB : SELECT

alt vaga não encontrada
  Controller --> UI : 404
else vaga encontrada
  note over Controller
    Não é DELETE físico:
    apenas vaga.ativo = False
  end note
  Controller -> ORM : vaga.ativo = False
  Controller -> DB : COMMIT
  Controller -> Cache : invalidate_vagas_cache()
  Controller -> Audit : registrar_auditoria("desativar_vaga")
  Audit -> DB : INSERT audit_logs
  Controller --> UI : 204 No Content
end
@enduml
```

### 8.6 Fluxo de consultas — histórico de movimentações (filtro)

```plantuml
@startuml Seq_Consulta
title Sequência — GET /movimentacoes?vaga_id=...&placa=... (consulta filtrada)

actor Usuário
participant "Hook (TanStack Query)" as Hook
participant "Router /movimentacoes" as Controller
participant "AsyncSession" as ORM
database "Banco" as DB

Usuário -> Hook : solicita histórico de uma vaga/placa
Hook -> Controller : GET /movimentacoes?vaga_id=S2-49
Controller -> Controller : Depends(get_current_user)
Controller -> ORM : select(Movimentacao)\n.where(vaga_id==...)\n.order_by(timestamp desc)\n.limit(200)
ORM -> DB : SELECT ... LIMIT 200
DB --> ORM : linhas
ORM --> Controller : list[Movimentacao]
Controller --> Hook : 200 list[MovimentacaoRead]
@enduml
```

### 8.7 Fluxo de tratamento de exceções — sincronização em lote

```plantuml
@startuml Atividade_Tratamento_Excecoes
!pragma layout smetana
title Atividade — POST /movimentacoes/sync (tolerância a falha parcial)

start
:Recebe lista de operações pendentes\n(fila Dexie do cliente);
:resultados := [];

while (há próxima operação no lote?) is (sim)
  :Identifica tipo da operação\n(entrada/saida/reserva/cancelamento);
  partition "try" {
    :Executa aplicar_* correspondente\n(services/sync.py);
  }
  if (RecursoNaoEncontradoError\nou ConflitoOperacaoError\nou ValidationError\nou KeyError?) then (sim)
    :db.rollback();
    :resultados.append({sucesso:false,\nmensagem: str(erro)});
  else (não)
    if (Exception genérica não prevista?) then (sim)
      :db.rollback();
      :logger.exception(...) — stack trace só no log,\nnão exposto ao cliente;
      :resultados.append({sucesso:false,\nmensagem:"Erro ao processar operação."});
    else (sucesso)
      :resultados.append({sucesso:true});
      :registrar_auditoria("sync_<tipo>");
    endif
  endif
endwhile (não — lote concluído)

:Retorna 200 com um resultado por operação\n(o cliente decide o que remover da fila\ne o que manter para nova tentativa);
stop
@enduml
```

**Raciocínio:** este é o único ponto do backend onde o tratamento de exceção é multi-nível e
explícito por design (`routers/movimentacoes.py:100-124`) — cada operação do lote é isolada (uma
falha não aborta as demais), com `rollback()` por item para não vazar estado parcial de uma operação
com falha para a próxima. Fora deste endpoint, o padrão do resto do backend é mais simples: exceções
de domínio (`RecursoNaoEncontradoError`/`ConflitoOperacaoError`) → `HTTPException` 404/409 (ver seções
8.3–8.5); qualquer outra exceção não tratada sobe para o handler padrão do FastAPI/Starlette (500, sem
handler customizado registrado em `main.py`).

### 8.8 Fluxo de inicialização da aplicação

Ver diagrama de atividade completo na seção 6.4.

---

## Limitações, divergências e perguntas em aberto

Itens abaixo **não puderam ser confirmados apenas pela leitura do código**, ou representam uma
divergência entre a intenção documentada em `PROJECT_SPEC.md` e o que o código efetivamente faz. Cada
um é sinalizado para que um desenvolvedor humano confirme antes de tratá-lo como fato ou como bug:

1. **Sem camada de Repositório explícita.** O acesso a dados é feito diretamente via `AsyncSession`
   dentro de routers e services. Isso é uma observação estrutural, não um erro — mas significa que
   não existe um ponto único para trocar a estratégia de persistência ou adicionar testes de
   contrato de repositório.
2. **Sem Use Cases como classes.** As regras de negócio estão em funções de módulo
   (`services/sync.py`). Funcionalmente equivalente a um caso de uso, mas não modelado como tal no
   código.
3. **Integridade "1 ocupante ativo por vaga" não é garantida pelo banco.** Não há `UNIQUE` em
   `ocupantes.vaga_id`; o invariante depende inteiramente da checagem de `Vaga.status` em
   `aplicar_entrada` (`services/sync.py:24-29`). Uma escrita concorrente sem passar por essa função,
   ou uma condição de corrida entre duas requisições simultâneas na mesma vaga, poderia (em teoria)
   criar dois registros de `ocupantes` para a mesma vaga — não foi possível confirmar se há algum
   lock/transação adicional que previna isso, pois não há teste de concorrência no diretório `tests/`.
4. **Coluna `movimentacoes.sincronizado` parece vestigial.** Existe na migração e no modelo (default
   `True`), mas nenhuma função em `services/sync.py` ou nos routers lidos altera esse valor para
   `False`, nem há leitura desse campo em nenhum filtro de consulta encontrado. A reconciliação
   "offline vs. já sincronizado" é feita inteiramente no cliente (Dexie), não neste campo do servidor.
   Não é possível confirmar, sem o autor do código, se essa coluna é um remanescente de um design
   anterior ou se está reservada para uso futuro.
5. **CRUD de `admin.py` não gera `audit_logs`.** Ao contrário de `vagas.py`/`reservas.py`/
   `movimentacoes.py`, nenhuma rota de `admin.py` (criar/remover domínio, criar/remover admin) chama
   `registrar_auditoria`. Ou seja, a tabela de auditoria existe, mas mudanças no controle de acesso
   (potencialmente a categoria mais sensível de mudança) não ficam auditadas.
6. **Regra de "upsert portátil via `session.merge()`"** (`PROJECT_SPEC.md`) **não encontrada no
   código lido.** Os pontos de criação observados usam `db.get(...)` seguido de `db.add(...)`
   condicional (ex.: `routers/admin.py:44-52`), não `session.merge()`. Pode ser que a regra do spec
   se refira a um padrão pretendido para código futuro, não implementado até este ponto.
7. **"Logging estruturado"** (regra do `PROJECT_SPEC.md`) — o `logging.basicConfig` usado
   (`main.py:15-18`) produz texto plano formatado, não JSON estruturado. Não há biblioteca de logging
   estruturado (ex. `structlog`, `python-json-logger`) nas dependências (`requirements.txt`).
8. **Regex de cache do Service Worker (`vite.config.ts:28`)** — `urlPattern: /^https:\/\/api\./`
   só casa origens que **literalmente começam com** `https://api.`. Se o domínio de produção do
   backend for o padrão gerado pelo Railway (ex. `algo.up.railway.app`, sem o subdomínio `api.`), essa
   regra de cache `NetworkFirst` nunca seria acionada — não foi possível confirmar qual será o domínio
   final de produção, pois isso depende de configuração feita fora do repositório (painel Railway).
9. **Papel exato de `pymysql` nas dependências** (`requirements.txt:9`) — o driver assíncrono
   efetivamente configurado para MySQL é `aiomysql` (`config.py:15`); não foi possível confirmar pela
   leitura do código se `pymysql` é usado por alguma dependência transitiva (possivelmente pelo
   Alembic em algum caminho síncrono) ou se é uma dependência não utilizada.
10. **Testes automatizados de frontend não existem**, apesar de `package.json` declarar
    `"test": "vitest run"` e o `PROJECT_SPEC.md` mencionar "Jest para componentes React críticos" — a
    busca por arquivos `*.test.*`/`*.spec.*` em `frontend/src` não retornou nenhum resultado. O
    workflow de CI também não roda nenhum comando de teste de frontend, apenas `npm run build`.
11. **Nenhuma tabela local de usuários.** A ausência de uma entidade "Usuário" no banco é uma
    característica de design (identidade 100% delegada ao Auth0), não uma omissão — mas é importante
    deixar explícito, já que o enunciado deste levantamento pergunta por entidades de domínio: não
    existe uma entidade `Usuario`/`Account` para modelar.
12. **Comportamento de infraestrutura externa não verificável estaticamente**: o conteúdo real da
    Auth0 Post-Login Action em produção, a configuração exata do template Railway da Evolution API, e
    o estado atual dos secrets/variáveis no dashboard Railway não são visíveis a partir do
    repositório — a documentação das seções 2, 3.6 e 6 sobre esses pontos reflete o que
    `PROJECT_SPEC.md`/`DEPLOY.md` descrevem como *intenção de configuração*, cruzado com o que o
    *código do backend* de fato consome (variáveis de ambiente, formato de headers) — não uma
    inspeção do painel em si.

Caso alguma dessas hipóteses precise ser resolvida com certeza (por exemplo, para decidir se o item 3
ou o item 4 é um bug a corrigir), recomenda-se confirmar com quem escreveu o código original ou
revisar o histórico de commits/PRs correspondente.
