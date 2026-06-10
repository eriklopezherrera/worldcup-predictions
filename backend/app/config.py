import json
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://wcadmin:devpassword@localhost:5433/worldcuppredictions"
    # When set (deployed environments), DATABASE_URL is built from this
    # Secrets Manager secret at cold start instead of the value above.
    db_secret_arn: str = ""
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


def _database_url_from_secret(secret_arn: str) -> str:
    """Build the asyncpg URL from an RDS-managed Secrets Manager secret."""
    import boto3

    raw = boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)
    secret = json.loads(raw["SecretString"])
    return (
        f"postgresql+asyncpg://{secret['username']}:{quote_plus(secret['password'])}"
        f"@{secret['host']}:{secret.get('port', 5432)}"
        f"/{secret.get('dbname', 'worldcuppredictions')}?ssl=require"
    )


settings = Settings()

if settings.db_secret_arn:
    settings.database_url = _database_url_from_secret(settings.db_secret_arn)
