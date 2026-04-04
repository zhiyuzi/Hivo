from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    trusted_issuers: str = "https://id.hivo.ink"
    club_url: str = "https://club.hivo.ink"
    database_path: str = "./data/acl.db"

    model_config = {"env_file": ".env"}


settings = Settings()
