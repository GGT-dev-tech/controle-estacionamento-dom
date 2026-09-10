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

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
