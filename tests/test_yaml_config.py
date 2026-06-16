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
