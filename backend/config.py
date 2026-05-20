from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase (warehouse project — acts as the auth/identity store for the portal)
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_ANON_KEY: str
    SUPABASE_JWT_SECRET: str

    # Resend (transactional email)
    RESEND_API_KEY: str
    EMAIL_FROM: str = "noreply@c-aui.com"

    # Portal developer (single portal manager who receives signup notifications + can approve)
    DEVELOPER_EMAIL: str = "pattanachok_msn@hotmail.com"

    # Public URL of the frontend (for email links)
    PORTAL_FRONTEND_URL: str = "https://c-aui.com"

    # CORS — allow localhost during dev + all c-aui.com subdomains
    CORS_ALLOW_ORIGIN_REGEX: str = r"^(http://localhost:\d+|https?://(.*\.)?c-aui\.com)$"

settings = Settings()
