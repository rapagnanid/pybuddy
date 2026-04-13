"""Tests for the CLI commands."""

from click.testing import CliRunner

from pybuddy.cli import cli


def test_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "analyze" in result.output
    assert "chat" in result.output
    assert "watch" in result.output
    assert "config" in result.output


def test_config_set_and_show(tmp_path, monkeypatch):
    # Use a temporary config directory
    monkeypatch.setattr("pybuddy.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("pybuddy.config.CONFIG_FILE", tmp_path / "config.toml")

    runner = CliRunner()

    # Set a value
    result = runner.invoke(cli, ["config", "set", "notify", "true"])
    assert result.exit_code == 0
    assert "✓" in result.output

    # Show config
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0
    assert "notify" in result.output


def test_analyze_offline(tmp_path):
    # Create a test file
    test_file = tmp_path / "test.py"
    test_file.write_text("import os\nfor i, row in df.iterrows():\n    pass\n")

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(test_file), "--offline"])
    assert result.exit_code == 0
    assert "os" in result.output
    assert "iterrows" in result.output


def test_analyze_missing_file():
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "nonexistent.py"])
    assert result.exit_code != 0
