from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # SMTP
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    FRONTEND_URL: str = "https://www.agenticx.co.in"
    CERTIFICATE_FRONTEND_URL: str = "https://certificate.agenticx.co.in"

    # Razorpay
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # JWT
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,https://agenticx.co.in,https://www.agenticx.co.in,https://agenticx-co-in.vercel.app,https://certificate.agenticx.co.in"

    # App Settings
    APP_NAME: str = "agenticx-backend"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    try:
        import socket
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(s.DATABASE_URL)
        if parsed.hostname:
            # Check if it's not already an IP address
            try:
                socket.inet_aton(parsed.hostname)
            except socket.error:
                # Resolve hostname to IPv4
                ip = socket.gethostbyname(parsed.hostname)
                netloc = parsed.netloc
                # If there's a port, handle it properly
                if parsed.port:
                    netloc = netloc.replace(f"{parsed.hostname}:{parsed.port}", f"{ip}:{parsed.port}")
                else:
                    netloc = netloc.replace(parsed.hostname, ip)
                s.DATABASE_URL = urlunparse(parsed._replace(netloc=netloc))
    except Exception as e:
        print(f"Warning: Failed to resolve database hostname to IPv4: {e}")
    return s


settings = get_settings()
