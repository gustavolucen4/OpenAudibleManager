from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "OpenAudible Manager"
    ENV: str = "development"
    PORT: int = 8085
    DATABASE_URL: str = "sqlite:///./auth.db"
    
    SECRET_KEY: str = "gU2b3LzX9-Y5pW8k1v4j7m0q3s6v9y2B5e8h1k4m7p0="
    ENCRYPTION_KEY: str = "gU2b3LzX9-Y5pW8k1v4j7m0q3s6v9y2B5e8h1k4m7p0="

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


settings = Settings()
