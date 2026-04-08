from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    trusted_issuers: str = "https://id.hivo.ink"
    database_path: str = "./data/club.db"
    acl_url: str = "https://acl.hivo.ink"

    model_config = {"env_file": ".env"}

    def trusted_issuers_list(self) -> list[str]:
        return [s.strip() for s in self.trusted_issuers.split(",") if s.strip()]


settings = Settings()
