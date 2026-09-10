from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Ambiente
    environment: str = "development"
    port: int = 8000
    frontend_url: str = "http://localhost:3000"
    api_host: str = "localhost"

    # Banco de dados
    database_url: str = "mysql+aiomysql://dom_user:dom_pass@localhost:3306/estacionamento"

    @field_validator("database_url")
    @classmethod
    def _normalizar_driver_async(cls, v: str) -> str:
        """Railway (e provedores similares) publicam DATABASE_URL sem o driver assíncrono
        explícito (ex.: `postgres://` ou `postgresql://`, nunca `postgresql+asyncpg://`).
        Normaliza aqui para que colar a variável do plugin funcione sem edição manual.
        """
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://") :]
        if v.startswith("mysql://"):
            v = "mysql+aiomysql://" + v[len("mysql://") :]
        return v

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Auth0
    auth0_domain: str = ""
    auth0_audience: str = ""
    auth0_client_id: str = ""
    auth0_client_secret: str = ""
    auth0_mgmt_client_id: str = ""
    auth0_mgmt_client_secret: str = ""

    # Evolution API
    evolution_api_url: str = ""
    evolution_api_key: str = ""
    evolution_instance_name: str = "dom-estacionamento"
    whatsapp_webhook_secret: str = ""

    # Resend
    resend_api_key: str = ""
    email_from: str = "noreply@dompagamentos.com.br"
    relatorio_destinatarios: str = ""  # e-mails separados por vírgula

    # Tarefas agendadas (Railway Cron ou similar) — autenticadas via header X-Cron-Secret
    cron_secret: str = ""

    # Auth0 Post-Login Action — autentica as chamadas de verificação de domínio/admin
    # via header X-Internal-Secret (o usuário ainda não tem JWT nesse ponto do login)
    auth0_action_secret: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
