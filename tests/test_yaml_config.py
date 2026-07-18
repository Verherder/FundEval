# -*- coding: UTF-8 -*-
"""Tests for YAML-backed configuration helpers."""

from src.config import yaml_config


def test_fund_refresh_config_defaults_to_five(monkeypatch):
    monkeypatch.setattr(yaml_config, "load_yaml_config", lambda: {})

    assert yaml_config.get_fund_refresh_config()["request_batch_size"] == 5


def test_fund_refresh_config_reads_positive_request_batch_size(monkeypatch):
    monkeypatch.setattr(
        yaml_config,
        "load_yaml_config",
        lambda: {"fund_refresh": {"request_batch_size": 8}},
    )

    assert yaml_config.get_fund_refresh_config()["request_batch_size"] == 8


def test_fund_refresh_config_rejects_non_positive_request_batch_size(monkeypatch):
    monkeypatch.setattr(
        yaml_config,
        "load_yaml_config",
        lambda: {"fund_refresh": {"request_batch_size": 0}},
    )

    assert yaml_config.get_fund_refresh_config()["request_batch_size"] == 5


def test_fund_refresh_config_caps_unsafe_concurrency(monkeypatch):
    monkeypatch.setattr(
        yaml_config,
        "load_yaml_config",
        lambda: {"fund_refresh": {"request_batch_size": 30}},
    )

    assert yaml_config.get_fund_refresh_config()["request_batch_size"] == 15


def test_save_refresh_settings_updates_yaml_atomically(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "# 保留注释\n"
        "page_refresh:\n"
        "  auto_refresh_interval: 60000  # 刷新间隔\n"
        "server:\n"
        "  port: 8312\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("FUNDEVAL_CONFIG", str(config_path))

    result = yaml_config.save_refresh_settings(False, 120000, 12)

    assert result == {
        "auto_refresh_enabled": False,
        "auto_refresh_interval": 120000,
        "request_batch_size": 12,
    }
    assert yaml_config.load_yaml_config()["server"]["port"] == 8312
    saved_content = config_path.read_text(encoding="utf-8")
    assert "# 保留注释" in saved_content
    assert "auto_refresh_interval: 120000  # 刷新间隔" in saved_content
