from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    llm_base_url: str = "http://localhost:1234/v1"
    llm_api_key: str = "lm-studio"
    llm_model: str = "local-model"
    context_limit: int = 8192
    max_tool_executions: int = 10
    max_tool_output_chars: int = 12000
    harness_workspace: str = "./workspace"
    database_url: str = "sqlite:///./data/harness.db"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
Path(settings.harness_workspace).mkdir(parents=True, exist_ok=True)
Path("./data").mkdir(parents=True, exist_ok=True)
