import json
import os
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import config
from app.cli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def temp_cli_config(monkeypatch, tmp_path):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setenv("MGOPS_CONFIG", str(cfg_file))
    return cfg_file


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "MongoDB Ops Console Command-Line Utility" in result.stdout
    assert "status" in result.stdout
    assert "clusters" in result.stdout
    assert "ops" in result.stdout
    assert "alerts" in result.stdout


def test_config_save_and_load():
    cfg = config.update_tokens("test-access-token", "test-refresh-token", api_url="http://testserver:8000")
    assert cfg["access_token"] == "test-access-token"
    assert cfg["refresh_token"] == "test-refresh-token"
    assert cfg["api_url"] == "http://testserver:8000"

    loaded = config.load_config()
    assert loaded["access_token"] == "test-access-token"
    assert loaded["refresh_token"] == "test-refresh-token"

    config.clear_tokens()
    cleared = config.load_config()
    assert cleared["access_token"] is None
    assert cleared["refresh_token"] is None


def test_subcommand_helps():
    for cmd in [["status", "--help"], ["clusters", "list", "--help"], ["ops", "restart-node", "--help"], ["alerts", "list", "--help"], ["audit", "list", "--help"]]:
        res = runner.invoke(app, cmd)
        assert res.exit_code == 0
