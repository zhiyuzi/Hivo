from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_path: str = "./data/drop.db"
    trusted_issuers: str = "https://id.agentinfra.cloud"  # comma-separated

    # Cloudflare R2 / S3-compatible
    r2_endpoint: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "agent-drop"

    # Limits
    max_file_size: int = 1024 * 1024  # 1 MB
    max_files_per_agent: int = 100

    model_config = {"env_file": ".env"}

    def trusted_issuers_list(self) -> list[str]:
        return [s.strip() for s in self.trusted_issuers.split(",") if s.strip()]


settings = Settings()
