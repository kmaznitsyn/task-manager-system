from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "user-service"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/users_db"

    # Keycloak / OIDC
    keycloak_issuer: str = "http://localhost:8080/realms/taskmanager"
    keycloak_audience: str = "taskmanager-api"
    keycloak_jwks_url: str = "http://localhost:8080/realms/taskmanager/protocol/openid-connect/certs"

    cors_origins: list[str] = ["http://localhost:4200", "https://taskmanager-ui-578910743970.europe-west3.run.app"]

    class Config:
        env_file = ".env"


settings = Settings()
