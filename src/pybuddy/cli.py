"""PyBuddy CLI — entry point for all commands."""

import click
from rich.console import Console

from pybuddy import __version__

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="PyBuddy")
def cli():
    """PyBuddy — Your sarcastic Python programming buddy."""
    pass


# --- config command group ---


@cli.group()
def config():
    """Manage PyBuddy configuration."""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set a configuration value (e.g., pybuddy config set api.key sk-ant-...)."""
    from pybuddy.config import set_config_value

    set_config_value(key, value)
    if "key" in key.lower():
        display = value[:8] + "..." if len(value) > 8 else value
    else:
        display = value
    console.print(f"[green]✓[/green] {key} = {display}")


@config.command("show")
def config_show():
    """Show current configuration."""
    from pybuddy.config import load_config

    cfg = load_config()
    console.print("[bold]PyBuddy Configuration[/bold]\n")
    for section, values in cfg.items():
        console.print(f"[cyan][{section}][/cyan]")
        for k, v in values.items():
            display = v
            if "key" in k.lower() and isinstance(v, str) and len(v) > 8:
                display = v[:8] + "..."
            console.print(f"  {k} = {display}")
        console.print()


# --- analyze command ---


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--offline", is_flag=True, help="Only use static analysis (no AI).")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON (for editor extensions).")
def analyze(file, offline, as_json):
    """Analyze a Python file or Jupyter notebook."""
    from pybuddy.commands.analyze import run_analyze

    run_analyze(file, offline=offline, as_json=as_json)


# --- chat command ---


@cli.command()
@click.argument("file", type=click.Path(exists=True), required=False)
def chat(file):
    """Start an interactive chat session about your code."""
    from pybuddy.commands.chat import run_chat

    run_chat(file)


# --- watch command ---


@cli.command()
@click.argument("directory", type=click.Path(exists=True), default=".")
@click.option("--notify", is_flag=True, help="Enable desktop notifications.")
def watch(directory, notify):
    """Watch a directory and analyze files on save."""
    from pybuddy.commands.watch import run_watch

    run_watch(directory, notify=notify)
