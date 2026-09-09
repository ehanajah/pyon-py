import subprocess
import sys

import click

from .utils.toml_utils import get_pyon_toml_path, remove_dependency


@click.command()
@click.argument("packages", nargs=-1, required=True)
def remove(packages):
    """Remove dependencies (pip uninstall + remove from pyon.toml)"""
    if not get_pyon_toml_path().exists():
        click.secho("Error: pyon.toml not found.", fg="red", err=True)
        sys.exit(1)

    # Uninstall via pip
    click.echo(f"Uninstalling packages: {', '.join(packages)}...")
    result = subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", *packages], check=False)

    if result.returncode != 0:
        click.secho("Failed to uninstall packages", fg="yellow")

    # Update pyon.toml
    for pkg in packages:
        if remove_dependency(pkg):
            click.secho(f"Successfully removed {pkg} from pyon.toml", fg="green")
        else:
            click.secho(f"{pkg} is not registered at pyon.toml", fg="yellow")
            