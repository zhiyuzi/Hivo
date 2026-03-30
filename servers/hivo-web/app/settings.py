from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    repo_url: str = "https://github.com/zhiyuzi/Hivo"

    model_config = {"env_file": ".env"}


settings = Settings()
