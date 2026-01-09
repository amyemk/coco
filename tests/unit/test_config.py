"""
Unit tests for configuration management
"""

import pytest
import tempfile
import yaml
from pathlib import Path

from src.config.settings import (
    Settings,
    AppConfig,
    UserProfile,
    BriefingConfig,
    GmailIntegrationConfig,
)


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing"""
    config_data = {
        "user": {
            "name": "Test User",
            "email": "test@example.com",
            "timezone": "America/New_York",
            "title": "CPO",
        },
        "briefing": {
            "delivery_time": "08:00",
            "delivery_method": "email",
        },
        "integrations": {
            "gmail": {
                "enabled": True,
                "sync_interval_minutes": 15,
            }
        },
        "ai": {
            "provider": "anthropic",
            "model": "claude-3-5-sonnet-20241022",
        },
        "storage": {
            "database_path": "./test_data/test.db",
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    yield config_path

    # Cleanup
    Path(config_path).unlink(missing_ok=True)


def test_load_config(temp_config_file):
    """Test loading configuration from file"""
    settings = Settings(config_path=temp_config_file)

    assert settings.config.user.name == "Test User"
    assert settings.config.user.email == "test@example.com"
    assert settings.config.briefing.delivery_time == "08:00"


def test_user_profile_validation():
    """Test user profile model validation"""
    profile = UserProfile(
        name="Jane Doe",
        email="jane@example.com",
        timezone="America/Los_Angeles",
        title="Chief Product Officer",
    )

    assert profile.name == "Jane Doe"
    assert profile.timezone == "America/Los_Angeles"


def test_briefing_config_validation():
    """Test briefing configuration validation"""
    config = BriefingConfig(
        delivery_time="07:00",
        delivery_method="email",
        max_priorities=10,
    )

    assert config.delivery_time == "07:00"
    assert config.max_priorities == 10


def test_invalid_delivery_time():
    """Test that invalid time format raises error"""
    with pytest.raises(ValueError):
        BriefingConfig(delivery_time="25:00")  # Invalid hour


def test_invalid_delivery_method():
    """Test that invalid delivery method raises error"""
    with pytest.raises(ValueError):
        BriefingConfig(delivery_method="invalid")


def test_integration_enabled_check(temp_config_file):
    """Test checking if integrations are enabled"""
    settings = Settings(config_path=temp_config_file)

    assert settings.is_integration_enabled("gmail") is True


def test_get_database_path(temp_config_file):
    """Test getting database path from config"""
    settings = Settings(config_path=temp_config_file)

    db_path = settings.get_database_path()
    assert "test.db" in db_path


def test_gmail_integration_config():
    """Test Gmail integration configuration"""
    config = GmailIntegrationConfig(
        enabled=True,
        sync_interval_minutes=15,
        max_results_per_sync=100,
        include_labels=["INBOX", "IMPORTANT"],
        priority_senders=["ceo@company.com"],
    )

    assert config.enabled is True
    assert config.sync_interval_minutes == 15
    assert "INBOX" in config.include_labels
    assert "ceo@company.com" in config.priority_senders
