import importlib.metadata
import subprocess
import sys

import click

from .utils.toml_utils import add_dependency, get_pyon_toml_path
from .utils.wasm_check import WasmStatus, check_wasm_compatible


def get_installed_version(package_name: str):
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return ""

@click.command()
@click.argument("packages", nargs=-1, required=True)
@click.option("--dev", is_flag=True, help="Add as a development dependency (local only)")
def add(packages, dev):
    """Add a package to the pyon.toml dependencies (pip install + add to pyon.toml)"""
    if not get_pyon_toml_path().exists():
        click.secho("Error: pyon.toml not found. Run 'pyon init' to create a new pyon.toml file.", fg="red", err=True)
        sys.exit(1)

    # WASM compatibility check
    if not dev:
        for pkg in packages:
            click.echo(f"Checking WASM compatibility for {pkg}...")
            status, msg = check_wasm_compatible(pkg)

            if status == WasmStatus.INCOMPATIBLE:
                click.secho(msg, fg="red", bold=True)
                click.confirm(f"'{pkg}' may not work in WASM/browser environments. Do you want to continue adding it?", abort=True)
            elif status == WasmStatus.UNKNOWN:
                click.secho(msg, fg="yellow")
            else:
                click.secho(msg, fg="green")

    # Install packages using pip
    click.echo(f"Installing packages: {', '.join(packages)}...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", *packages], check=False)

    if result.returncode != 0:
        click.secho("Failed to install pacakges via pip", fg="red", err=True)
        sys.exit(1)

    for pkg in packages:
        version = get_installed_version(pkg)
        add_dependency(pkg, version, is_dev=dev)
        click.secho(f" Successfully added {pkg}=={version} to {'dev-dependencies' if dev else 'dependencies'} in pyon.toml", fg="blue")
    