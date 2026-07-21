from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    GEMINI_API_KEY: str
    FIREBASE_PROJECT_ID: str
    SECRET_KEY: str = "change-this-in-production"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    FIREBASE_SERVICE_ACCOUNT: str = ""

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET: str = ""
    S3_ENDPOINT_URL: str = ""
    S3_REGION: str = "auto"

    # Per-user rate limits for the expensive endpoints. Values are limit strings
    # understood by slowapi/limits (e.g. "10/hour", "5/minute") and can be tuned
    # via environment variables without a redeploy. Set RATE_LIMIT_ENABLED=false
    # to turn limiting off entirely.
    RATE_LIMIT_ENABLED: bool = True
    QUIZ_GENERATION_RATE_LIMIT: str = "10/hour"
    FLASHCARD_GENERATION_RATE_LIMIT: str = "10/hour"
    NOTE_UPLOAD_RATE_LIMIT: str = "20/hour"

    # Origins allowed to call the API from a browser, as a comma-separated list.
    # Kept as a string rather than list[str] because pydantic-settings decodes
    # complex types from env as JSON, which would reject a plain comma list.
    # Read it through `allowed_origins` below, never directly.
    ALLOWED_ORIGINS: str = (
        "http://localhost:3000,"
        "https://circles-9ez5.vercel.app,"
        "https://staging-circles-sam-9d919e89.vercel.app,"
        "circles-mocha-tau.vercel.app"
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = ".env"

settings = Settings()
