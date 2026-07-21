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

    class Config:
        env_file = ".env"

settings = Settings()
