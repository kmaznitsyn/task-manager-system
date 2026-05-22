from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "task-service"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/tasks_db"

    keycloak_issuer: str = "http://localhost:8080/realms/taskmanager"
    keycloak_audience: str = "taskmanager-api"
    keycloak_jwks_url: str = "http://localhost:8080/realms/taskmanager/protocol/openid-connect/certs"

    # Pub/Sub — disabled by default for local dev. Either set
    # PUBSUB_EMULATOR_HOST (emulator), or PUBSUB_ENABLED=1 (real GCP).
    pubsub_enabled: bool = False
    pubsub_project_id: str = "local-dev"
    pubsub_topic_tasks_events: str = "tasks-events"

    cors_origins: list[str] = ["http://localhost:4200", "https://taskmanager-ui-578910743970.europe-west3.run.app"]

    class Config:
        env_file = ".env"


settings = Settings()
