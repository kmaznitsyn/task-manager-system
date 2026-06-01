from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "docs-service"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/docs_db"

    keycloak_issuer: str = "http://localhost:8080/realms/taskmanager"
    keycloak_audience: str = "taskmanager-api"
    keycloak_jwks_url: str = "http://localhost:8080/realms/taskmanager/protocol/openid-connect/certs"

    # Pub/Sub — same opt-in semantics as task-service. Local dev logs only.
    pubsub_enabled: bool = False
    pubsub_project_id: str = "local-dev"
    pubsub_topic_documents_events: str = "documents-events"

    cors_origins: list[str] = [
        "http://localhost:4200",
        "https://taskmanager-ui-578910743970.europe-west3.run.app",
    ]

    class Config:
        env_file = ".env"


settings = Settings()
