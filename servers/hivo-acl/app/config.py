from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    trusted_issuers: str = "https://id.hivo.ink"
    club_internal_url: str = "http://127.0.0.1:8003"
    database_path: str = "./data/acl.db"

    model_config = {"env_file": ".env"}


settings = Settings()
