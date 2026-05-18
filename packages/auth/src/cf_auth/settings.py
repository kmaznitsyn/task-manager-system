from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    keycloak_issuer: str
    keycloak_audience: str
    keycloak_jwks_url: str
    jwks_cache_ttl: int = 600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
    )
