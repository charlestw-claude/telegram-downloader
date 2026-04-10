"""Tests for configuration module."""

import os
from pathlib import Path

from src.core.config import Config


def test_config_defaults():
    config = Config()
    assert config.api_id == 0
    assert config.api_hash == ""
    assert config.phone is None
    assert config.max_concurrent_downloads == 3
    assert config.max_retries == 3
    assert config.check_interval == 300
    assert config.log_level == "INFO"


def test_config_validate_empty():
    config = Config()
    errors = config.validate()
    assert len(errors) == 2
    assert any("API_ID" in e for e in errors)
    assert any("API_HASH" in e for e in errors)


def test_config_validate_valid():
    config = Config(api_id=12345, api_hash="abc123")
    errors = config.validate()
    assert len(errors) == 0


def test_config_ensure_directories(tmp_path):
    config = Config(
        download_path=tmp_path / "downloads",
        log_dir=tmp_path / "logs",
    )
    config.ensure_directories()
    assert (tmp_path / "downloads").exists()
    assert (tmp_path / "logs").exists()


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "testhash")
    monkeypatch.setenv("TELEGRAM_PHONE", "+886912345678")
    monkeypatch.setenv("MAX_CONCURRENT_DOWNLOADS", "5")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    config = Config.from_env()
    assert config.api_id == 12345
    assert config.api_hash == "testhash"
    assert config.phone == "+886912345678"
    assert config.max_concurrent_downloads == 5
    assert config.log_level == "DEBUG"


def test_config_from_env_invalid_int(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "not_a_number")
    monkeypatch.setenv("MAX_CONCURRENT_DOWNLOADS", "bad")

    config = Config.from_env()
    assert config.api_id == 0
    assert config.max_concurrent_downloads == 3
