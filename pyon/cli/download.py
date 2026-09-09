import subprocess
import sys
from pathlib import Path

import click
import tomlkit

from .utils.lock_utils import generate_lock_file
from .utils.toml_utils import get_pyon_toml_path, read_pyon_toml, write_pyon_toml


@click.command()
@click.option("--packages-only", is_flag=True, help="Only download packages/wheels")
@click.option("--pyodide-only", is_flag=True, help="Only download Pyodide")
def download(packages_only, pyodide_only):
    """Download packages (WASM-compatible) and Pyodide"""
    toml_path = get_pyon_toml_path()
    if not toml_path.exists():
        click.secho("Error: pyon.toml not found. Run 'pyon init' to create a new pyon.toml file.", fg="red", err=True)
        sys.exit(1)

    doc = read_pyon_toml()

    do_packages = packages_only or (not packages_only and not pyodide_only)
    do_pyodide = pyodide_only or (not packages_only and not pyodide_only)

    if do_packages:
        click.echo("Sync packages...")
        all_packages = []
        all_packages.extend(doc.get("dependencies", {}).get("packages", []))
        all_packages.extend(doc.get("dev-dependencies", {}).get("packages", []))
        if all_packages:
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", *all_packages], check=False)
        
        click.echo("\nDownloading Pure Python wheels...")
        runtime_packages = doc.get("dependencies", {}).get("packages", [])

        if not runtime_packages:
            click.secho("No packages registered at [dependencies] block.", fg="yellow")
        else:
            cache_dir = Path.cwd() / "packages_cache"
            cache_dir.mkdir(exist_ok=True)

            cmd = [
                sys.executable, "-m", "pip", "download",
                "--only-binary=:all:",
                "--platform", "any",
                "--python-version", "3.11",
                "-d", str(cache_dir),
            ] + list(runtime_packages)

            result = subprocess.run(cmd, check=False)
            if result.returncode == 0:
                lock_path = Path.cwd() / "pyon.lock"
                generate_lock_file(cache_dir, lock_path)
                click.secho(f"\nSuccessfully download wheels and generated lock file: {lock_path.name}", fg="green")
            else:
                click.secho("\nProcess cancelled. Some dependencies may depend on C extensions (have no Pure Python wheel).", fg="red")

    if do_pyodide:
        click.echo("\nNot implemented yet.")