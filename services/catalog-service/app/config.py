import base64
import hashlib
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


SERVICE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = SERVICE_DIR.parents[1] if len(SERVICE_DIR.parents) > 1 else SERVICE_DIR
INSECURE_JWT_SECRETS = {
    "",
    "change-me",
    "change-me-access",
    "cross-border-api-secret",
    "dev-only-not-for-production-change-me",
}
INSECURE_DATABASE_PASSWORDS = {
    "",
    "password",
    "postgres",
    "dev-only-postgres-password",
}


class Settings(BaseSettings):
    app_name: str = "Cross Border Catalog Service"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/cross_border"
    jwt_secret: str = "change-me-access"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
    media_path: str | None = None
    supply_chain_csv_path: str | None = None
    media_url_path: str = "/media"
    frontend_url: str = "http://localhost:3000"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    secure_cookies: bool | None = None
    auth_body_max_bytes: int = 16_384
    password_min_characters: int = 12
    password_max_characters: int = 128
    login_failure_limit: int = 5
    login_lockout_seconds: int = 900
    login_rate_limit: int = 10
    login_rate_window_seconds: int = 60
    login_account_rate_limit: int = 20
    login_account_rate_window_seconds: int = 900
    register_rate_limit: int = 5
    register_rate_window_seconds: int = 3600
    refresh_rate_limit: int = 60
    refresh_rate_window_seconds: int = 60
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    privileged_mfa_required: bool = True
    mfa_encryption_key: str | None = None
    mfa_issuer: str = "SourceAI"
    mfa_challenge_seconds: int = 300
    mfa_challenge_attempt_limit: int = 5
    request_log_level: str = "INFO"
    error_monitoring_dsn: str | None = None
    error_monitoring_environment: str | None = None
    error_monitoring_traces_sample_rate: float = 0.05
    release_version: str | None = None
    notification_sender_name: str = "SourceAI"
    notification_dispatch_batch_size: int = 50
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_starttls: bool = True
    sms_webhook_url: str | None = None
    sms_api_token: str | None = None
    sms_sender_id: str | None = None
    whatsapp_webhook_url: str | None = None
    whatsapp_api_token: str | None = None
    whatsapp_sender_id: str | None = None
    payment_proof_allowed_hosts: str = ""
    automation_webhook_url: str | None = None
    automation_webhook_token: str | None = None
    automation_timeout_seconds: float = 12.0

    model_config = SettingsConfigDict(
        env_prefix="CATALOG_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_v3(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    def resolved_media_path(self) -> Path:
        if self.media_path:
            return Path(self.media_path)
        return SERVICE_DIR / "media"

    def resolved_supply_chain_csv_path(self) -> Path:
        if self.supply_chain_csv_path:
            return Path(self.supply_chain_csv_path)
        return ROOT_DIR / "Data" / "supply_chain_data.csv"

    def resolved_mfa_encryption_key(self) -> bytes:
        if self.mfa_encryption_key:
            return self.mfa_encryption_key.encode("ascii")
        # Development-only convenience. Production validation requires a
        # separately generated Fernet key so MFA secrets are not tied to JWTs.
        digest = hashlib.sha256(f"development-mfa:{self.jwt_secret}".encode()).digest()
        return base64.urlsafe_b64encode(digest)

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"production", "prod"}

    @property
    def allowed_browser_origins(self) -> tuple[str, ...]:
        values = [item.strip() for item in self.cors_origins.split(",") if item.strip() and item.strip() != "*"]
        values.append(self.frontend_url.strip())
        if not self.is_production:
            values.extend(
                (
                    "http://localhost:3000",
                    "http://127.0.0.1:3000",
                    "http://localhost:3001",
                    "http://127.0.0.1:3001",
                    "http://localhost:8000",
                    "http://127.0.0.1:8000",
                    "http://localhost:8001",
                    "http://127.0.0.1:8001",
                )
            )
        return tuple(dict.fromkeys(value.rstrip("/") for value in values if value))

    def cookie_secure_for_scheme(self, scheme: str) -> bool:
        if self.secure_cookies is not None:
            return self.secure_cookies
        return self.is_production or scheme.lower() == "https"

    def validate_runtime_security(self) -> None:
        if not self.is_production:
            return

        errors: list[str] = []
        normalized_secret = self.jwt_secret.strip()
        if normalized_secret in INSECURE_JWT_SECRETS or len(normalized_secret) < 32:
            errors.append("CATALOG_JWT_SECRET must be a unique random value of at least 32 characters")

        parsed_database = urlsplit(self.database_url)
        if parsed_database.scheme.startswith("postgres"):
            database_password = parsed_database.password or ""
            if database_password in INSECURE_DATABASE_PASSWORDS:
                errors.append("CATALOG_DATABASE_URL must not use a default or empty database password")

        if any(item.strip() == "*" for item in self.cors_origins.split(",")):
            errors.append("CATALOG_CORS_ORIGINS must be an explicit production allowlist")
        if self.secure_cookies is False:
            errors.append("CATALOG_SECURE_COOKIES must not be false in production")
        if not self.privileged_mfa_required:
            errors.append("CATALOG_PRIVILEGED_MFA_REQUIRED must be true in production")
        if not self.mfa_encryption_key:
            errors.append("CATALOG_MFA_ENCRYPTION_KEY must be a separately generated Fernet key")
        else:
            try:
                decoded_mfa_key = base64.b64decode(
                    self.mfa_encryption_key.encode("ascii"),
                    altchars=b"-_",
                    validate=True,
                )
            except (UnicodeEncodeError, ValueError):
                decoded_mfa_key = b""
            if len(decoded_mfa_key) != 32:
                errors.append("CATALOG_MFA_ENCRYPTION_KEY must be a valid Fernet key")
            if self.mfa_encryption_key == self.jwt_secret:
                errors.append("CATALOG_MFA_ENCRYPTION_KEY must be distinct from CATALOG_JWT_SECRET")
        if not 8 <= self.password_min_characters <= self.password_max_characters <= 256:
            errors.append("Password length bounds are invalid")
        if self.login_failure_limit < 3 or self.login_lockout_seconds < 60:
            errors.append("Persistent account lockout settings are too weak")
        if not self.allowed_browser_origins:
            errors.append("At least one browser origin must be configured")
        if self.request_log_level.strip().upper() not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            errors.append("CATALOG_REQUEST_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        if not self.error_monitoring_dsn:
            errors.append("CATALOG_ERROR_MONITORING_DSN is required in production")
        elif not self.error_monitoring_dsn.startswith("https://"):
            errors.append("CATALOG_ERROR_MONITORING_DSN must use HTTPS")
        if not 0 <= self.error_monitoring_traces_sample_rate <= 1:
            errors.append("CATALOG_ERROR_MONITORING_TRACES_SAMPLE_RATE must be between 0 and 1")
        if not 1 <= self.notification_dispatch_batch_size <= 50:
            errors.append("CATALOG_NOTIFICATION_DISPATCH_BATCH_SIZE must be between 1 and 50")
        if self.smtp_host and not self.smtp_from_email:
            errors.append("CATALOG_SMTP_FROM_EMAIL is required when SMTP is configured")
        if self.smtp_host and not self.smtp_starttls:
            errors.append("CATALOG_SMTP_STARTTLS must be true in production")
        for channel, webhook_url, api_token in (
            ("SMS", self.sms_webhook_url, self.sms_api_token),
            ("WhatsApp", self.whatsapp_webhook_url, self.whatsapp_api_token),
        ):
            if bool(webhook_url) != bool(api_token):
                errors.append(f"{channel} webhook URL and API token must be configured together")
            if webhook_url:
                parsed_webhook = urlsplit(webhook_url)
                if (
                    parsed_webhook.scheme != "https"
                    or not parsed_webhook.netloc
                    or parsed_webhook.username
                    or parsed_webhook.password
                ):
                    errors.append(f"{channel} provider webhook must use HTTPS")
        if not self.payment_proof_allowed_hosts.strip():
            errors.append(
                "CATALOG_PAYMENT_PROOF_ALLOWED_HOSTS must list approved HTTPS object-storage hosts"
            )
        if bool(self.automation_webhook_url) != bool(self.automation_webhook_token):
            errors.append("Automation webhook URL and token must be configured together")
        if self.automation_webhook_url:
            parsed_automation = urlsplit(self.automation_webhook_url)
            if (
                parsed_automation.scheme != "https"
                or not parsed_automation.netloc
                or parsed_automation.username
                or parsed_automation.password
            ):
                errors.append("CATALOG_AUTOMATION_WEBHOOK_URL must use HTTPS in production")
        if not 1 <= self.automation_timeout_seconds <= 30:
            errors.append("CATALOG_AUTOMATION_TIMEOUT_SECONDS must be between 1 and 30")
        for origin in self.allowed_browser_origins:
            parsed_origin = urlsplit(origin)
            if (
                parsed_origin.scheme != "https"
                or not parsed_origin.netloc
                or parsed_origin.username
                or parsed_origin.password
                or parsed_origin.path not in {"", "/"}
                or parsed_origin.query
                or parsed_origin.fragment
            ):
                errors.append(f"Production browser origin must use HTTPS: {origin}")

        if errors:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_runtime_security()
    return settings
