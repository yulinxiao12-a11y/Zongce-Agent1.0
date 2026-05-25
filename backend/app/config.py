from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./zongce_agent.db"
    upload_dir: str = "uploads"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_text_model: str = "gpt-4.1-mini"
    ai_vision_model: str = "gpt-4.1-mini"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
