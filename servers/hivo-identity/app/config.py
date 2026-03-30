from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    issuer_url: str = "https://id.hivo.ink"
    database_path: str = "./data/identity.db"
    signing_key_alg: str = "EdDSA"

    model_config = {"env_file": ".env"}


settings = Settings()
