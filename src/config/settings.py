"""
Configuration Management

Loads and validates configuration from:
- config.yaml file
- Environment variables
- Provides type-safe access to settings
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import time

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import structlog

logger = structlog.get_logger()


# ============================================================================
# Pydantic Models for Configuration
# ============================================================================


class CommunicationPreferences(BaseModel):
    """User communication preferences"""

    tone: str = "professional"  # professional, casual, friendly
    style: str = "concise"  # concise, detailed, balanced
    signature: str = ""


class UserProfile(BaseModel):
    """User profile configuration"""

    name: str
    email: str
    timezone: str = "America/Los_Angeles"
    title: str = "Chief Product Officer"
    communication: CommunicationPreferences = Field(
        default_factory=CommunicationPreferences
    )


class TriageRunConfig(BaseModel):
    """Configuration for a single triage run (noon or afternoon)"""

    enabled: bool = True
    time: str = "12:00"
    retry_on_failure: bool = True
    max_retries: int = 3
    flag_eod_urgency: bool = False  # Afternoon run only

    @field_validator("time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        try:
            time.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid time format: {v}. Use HH:MM format.")


class TriageNotificationConfig(BaseModel):
    """Notification email sent when pre-processing completes"""

    enabled: bool = True
    recipient: str = ""


class TriageJunkConfig(BaseModel):
    auto_queue_threshold: float = 0.95
    sender_memory: bool = True


class TriageNewsletterConfig(BaseModel):
    deduplicate_across_sources: bool = True
    track_engagement: bool = True
    engagement_review_weeks: int = 4


class TriageDraftConfig(BaseModel):
    options_count: int = 3
    save_to_gmail_drafts: bool = True


class TriageConfig(BaseModel):
    """Twice-daily triage configuration"""

    noon_run: TriageRunConfig = Field(
        default_factory=lambda: TriageRunConfig(time="12:00")
    )
    afternoon_run: TriageRunConfig = Field(
        default_factory=lambda: TriageRunConfig(time="16:00", flag_eod_urgency=True)
    )
    notification_email: TriageNotificationConfig = Field(
        default_factory=TriageNotificationConfig
    )
    junk: TriageJunkConfig = Field(default_factory=TriageJunkConfig)
    newsletters: TriageNewsletterConfig = Field(default_factory=TriageNewsletterConfig)
    drafts: TriageDraftConfig = Field(default_factory=TriageDraftConfig)
    max_junk_suggestions: int = 20
    max_newsletter_summaries: int = 10
    max_action_emails: int = 15


class SystemNotificationSendersConfig(BaseModel):
    """Known sender patterns for each DS system"""

    concur: List[str] = Field(
        default_factory=lambda: ["@concur.com", "noreply@concursolutions.com"]
    )
    sap: List[str] = Field(default_factory=lambda: ["@sap.com"])
    bob: List[str] = Field(
        default_factory=lambda: ["@hibob.com", "noreply@hibob.com"]
    )
    asana: List[str] = Field(
        default_factory=lambda: ["noreply@asana.com", "mail@asana.com"]
    )


class GmailIntegrationConfig(BaseModel):
    """Gmail integration configuration"""

    enabled: bool = True
    sync_interval_minutes: int = 15
    initial_sync_days: int = 30
    max_results_per_sync: int = 100
    include_labels: List[str] = Field(default_factory=lambda: ["INBOX", "IMPORTANT"])
    exclude_labels: List[str] = Field(default_factory=lambda: ["SPAM", "TRASH"])
    priority_senders: List[str] = Field(default_factory=list)
    priority_keywords: List[str] = Field(default_factory=list)
    system_notification_senders: SystemNotificationSendersConfig = Field(
        default_factory=SystemNotificationSendersConfig
    )


class CalendarIntegrationConfig(BaseModel):
    """Google Calendar integration configuration"""

    enabled: bool = True
    sync_interval_minutes: int = 30
    lookahead_days: int = 7
    lookback_days: int = 1
    calendars: List[str] = Field(default_factory=lambda: ["primary"])
    extract_actions_from: List[str] = Field(
        default_factory=lambda: ["1:1", "team meeting", "planning", "review"]
    )


class CodaDocConfig(BaseModel):
    """Individual Coda document configuration"""

    id: str
    name: str
    type: str  # roadmap, okrs, strategy, etc.
    priority: str = "high"


class CodaIntegrationConfig(BaseModel):
    """Coda integration configuration"""

    enabled: bool = True
    sync_interval_minutes: int = 60
    tracked_docs: List[CodaDocConfig] = Field(default_factory=list)
    track_changes: bool = True
    summarize_changes: bool = True


class IntegrationsConfig(BaseModel):
    """All external integrations"""

    gmail: GmailIntegrationConfig = Field(default_factory=GmailIntegrationConfig)
    calendar: CalendarIntegrationConfig = Field(
        default_factory=CalendarIntegrationConfig
    )
    coda: CodaIntegrationConfig = Field(default_factory=CodaIntegrationConfig)


class AIModelsConfig(BaseModel):
    """Model selection by task — haiku for volume, sonnet for quality"""

    classification: str = "claude-haiku-4-5-20251001"
    system_notification: str = "claude-haiku-4-5-20251001"
    junk_detection: str = "claude-haiku-4-5-20251001"
    newsletter_summary: str = "claude-sonnet-4-6"
    email_draft: str = "claude-sonnet-4-6"
    context_synthesis: str = "claude-sonnet-4-6"


class AIConfig(BaseModel):
    """AI/LLM configuration"""

    provider: str = "anthropic"
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 4000
    temperature: float = 0.7
    enable_caching: bool = True
    cache_ttl_hours: int = 24
    track_usage: bool = True
    monthly_budget_usd: float = 100.0
    models: AIModelsConfig = Field(default_factory=AIModelsConfig)


class RetentionConfig(BaseModel):
    """Data retention policies"""

    emails_days: Optional[int] = 90
    calendar_events_days: Optional[int] = 60
    tasks_completed_days: Optional[int] = 30
    decisions_days: Optional[int] = None  # Keep forever
    briefings_days: Optional[int] = 180


class StorageConfig(BaseModel):
    """Storage configuration"""

    database_path: str = "./data/coco.db"
    # Obsidian vault integration
    obsidian_vault_path: str = ""
    obsidian_backlog_file: str = "tasks/Backlog.md"
    obsidian_task_tag: str = "#coco"
    # Vector store
    vector_store_path: str = "./data/vectors"
    embedding_model: str = "text-embedding-3-small"
    backup_enabled: bool = True
    backup_path: str = "./backups"
    backup_interval_hours: int = 24
    backup_retention_days: int = 30
    retention: RetentionConfig = Field(default_factory=RetentionConfig)


class LogFileConfig(BaseModel):
    """Log file configuration"""

    path: str = "./logs/app.log"
    rotation: str = "daily"  # daily, weekly, size
    max_size_mb: int = 100
    retention_days: int = 30


class LoggingConfig(BaseModel):
    """Logging configuration"""

    level: str = "INFO"
    format: str = "json"  # json or text
    output: str = "both"  # file, console, or both
    file: LogFileConfig = Field(default_factory=LogFileConfig)
    log_api_calls: bool = True
    log_ai_prompts: bool = False
    log_ai_responses: bool = False


class AlertsConfig(BaseModel):
    """Alert configuration"""

    email_on_failure: bool = True
    alert_email: str = ""


class MonitoringConfig(BaseModel):
    """Monitoring configuration"""

    enable_metrics: bool = True
    metrics_port: int = 9090
    health_check_interval_minutes: int = 15
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)


class JobConfig(BaseModel):
    """Individual scheduled job configuration"""

    enabled: bool = True
    time: Optional[str] = None  # For daily jobs (HH:MM format)
    interval_minutes: Optional[int] = None  # For interval jobs
    retry_on_failure: bool = True
    max_retries: int = 3


class SchedulerConfig(BaseModel):
    """Scheduler configuration"""

    timezone: str = "America/Los_Angeles"
    jobs: Dict[str, JobConfig] = Field(
        default_factory=lambda: {
            "noon_triage": JobConfig(time="12:00"),
            "afternoon_triage": JobConfig(time="16:00"),
            "gmail_sync": JobConfig(interval_minutes=15, time=None),
            "calendar_sync": JobConfig(interval_minutes=30, time=None),
            "coda_sync": JobConfig(interval_minutes=60, time=None),
            "database_backup": JobConfig(time="02:00"),
        }
    )


class FeaturesConfig(BaseModel):
    """Feature flags by phase"""

    # Phase 3
    email_classification: bool = True
    junk_detection: bool = True
    system_notification_parsing: bool = True
    newsletter_summarization: bool = True
    email_draft_generation: bool = True
    obsidian_task_writing: bool = True
    # Phase 4+
    triage_session_state: bool = False
    gmail_draft_saving: bool = False
    junk_sender_memory: bool = False
    newsletter_engagement_tracking: bool = False
    meeting_action_extraction: bool = True
    coda_change_detection: bool = True
    weekly_summaries: bool = False
    web_ui: bool = False


class AdvancedConfig(BaseModel):
    """Advanced settings"""

    max_concurrent_api_calls: int = 5
    request_timeout_seconds: int = 30
    max_thread_depth: int = 20
    ignore_automated_emails: bool = True
    max_context_tokens: int = 100000
    context_compression: bool = True
    collect_feedback: bool = True
    feedback_retention_days: int = 365


class AppConfig(BaseModel):
    """Complete application configuration"""

    user: UserProfile
    triage: TriageConfig = Field(default_factory=TriageConfig)
    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)


class EnvSettings(BaseSettings):
    """
    Environment variables loaded from .env file
    """

    # API Keys
    anthropic_api_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    coda_api_token: str = ""

    # Security
    database_encryption_key: str = ""

    # Email/SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    sendgrid_api_key: str = ""

    # Application
    environment: str = "development"
    log_level: str = "INFO"
    app_name: str = "AI Chief of Staff"
    app_version: str = "1.0.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# ============================================================================
# Configuration Loading
# ============================================================================


class Settings:
    """
    Main settings class that combines YAML config and environment variables
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize settings from config file and environment.

        Args:
            config_path: Path to config.yaml file. If None, uses default location.
        """
        # Load environment variables
        self.env = EnvSettings()

        # Determine config file path
        if config_path is None:
            config_path = self._find_config_file()

        # Load YAML configuration
        self.config = self._load_config(config_path)

        logger.info(
            "settings_loaded",
            config_path=config_path,
            environment=self.env.environment,
        )

    def _find_config_file(self) -> Path:
        """
        Find config.yaml file in standard locations.

        Returns:
            Path to config file

        Raises:
            FileNotFoundError: If config file not found
        """
        # Try multiple locations
        possible_paths = [
            Path("config/config.yaml"),
            Path("config.yaml"),
            Path(__file__).parent.parent.parent / "config" / "config.yaml",
        ]

        for path in possible_paths:
            if path.exists():
                return path

        raise FileNotFoundError(
            "config.yaml not found. Please copy config.example.yaml to config.yaml"
        )

    def _load_config(self, config_path: Path) -> AppConfig:
        """
        Load and validate YAML configuration.

        Args:
            config_path: Path to config file

        Returns:
            Validated configuration

        Raises:
            ValueError: If configuration is invalid
        """
        with open(config_path, "r") as f:
            config_dict = yaml.safe_load(f)

        # Validate using Pydantic
        return AppConfig(**config_dict)

    def get_database_path(self) -> str:
        """Get database file path"""
        return self.config.storage.database_path

    def get_vector_store_path(self) -> str:
        """Get vector store path"""
        return self.config.storage.vector_store_path

    def get_obsidian_backlog_path(self) -> str:
        """Get full path to Obsidian backlog file"""
        import os
        return os.path.join(
            self.config.storage.obsidian_vault_path,
            self.config.storage.obsidian_backlog_file,
        )

    def is_integration_enabled(self, integration: str) -> bool:
        """
        Check if an integration is enabled.

        Args:
            integration: Integration name (gmail, calendar, coda)

        Returns:
            True if enabled
        """
        integrations_map = {
            "gmail": self.config.integrations.gmail.enabled,
            "calendar": self.config.integrations.calendar.enabled,
            "coda": self.config.integrations.coda.enabled,
        }
        return integrations_map.get(integration, False)

    def is_feature_enabled(self, feature: str) -> bool:
        """
        Check if a feature is enabled.

        Args:
            feature: Feature name

        Returns:
            True if enabled
        """
        return getattr(self.config.features, feature, False)


# Global settings instance
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get the global settings instance.

    Returns:
        Settings instance

    Raises:
        RuntimeError: If settings not initialized
    """
    if _settings_instance is None:
        raise RuntimeError("Settings not initialized. Call init_settings() first.")
    return _settings_instance


def init_settings(config_path: Optional[str] = None) -> Settings:
    """
    Initialize the global settings instance.

    Args:
        config_path: Optional path to config file

    Returns:
        Settings instance
    """
    global _settings_instance
    _settings_instance = Settings(config_path)
    return _settings_instance
