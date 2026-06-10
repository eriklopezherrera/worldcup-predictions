from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://wcadmin:devpassword@localhost:5433/worldcuppredictions"
    redis_url: str = "redis://localhost:6380/0"
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = "us-east-1"
    football_api_key: str = ""
    football_league_ids: str = "1"      # comma-separated; 1 = FIFA World Cup
    football_seasons: str = "2026"      # comma-separated
    allowed_origins: list[str] = ["http://localhost:5173"]
    environment: str = "dev"
    mock_auth: bool = False

    def get_league_ids(self) -> list[int]:
        return [int(x.strip()) for x in self.football_league_ids.split(",") if x.strip()]

    def get_seasons(self) -> list[int]:
        return [int(x.strip()) for x in self.football_seasons.split(",") if x.strip()]

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
