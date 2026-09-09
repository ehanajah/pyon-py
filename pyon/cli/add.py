import importlib.metadata
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import click

from .utils.lock_utils import generate_lock_file
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

    packages_cache_dir = Path.cwd() / "packages_cache"
    lock_path = Path.cwd() / "pyon.lock"

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
                click.echo(f"Testing download Pure Python wheels for '{pkg}' with dependencies...")

                with tempfile.TemporaryDirectory() as temp_dir:
                    cmd = [
                        sys.executable, "-m", "pip", "download",                                                               
                        "--only-binary=:all:",
                        "--platform", "any",
                        "--python-version", "3.11",
                        "-d", temp_dir,
                        pkg 
                    ]

                    result = subprocess.run(cmd, check=False, capture_output=True, text=True)

                    if result.returncode != 0:
                        click.secho(f"Failed: '{pkg}' or its transitive dependencies depend on C extension (has no pure python wheel).", fg="red")
                        click.echo("Use --dev argument if only for development usage.")
                        sys.exit(1)

                    packages_cache_dir.mkdir(exist_ok=True)
                    for wheel_file in Path(temp_dir).glob("*.whl"):
                        target_file = packages_cache_dir / wheel_file.name
                        if not target_file.exists():
                            shutil.copy(wheel_file, target_file)

                    click.secho(f"'{pkg}' is validated and cached at {packages_cache_dir}", fg="green")

        if packages_cache_dir.exists() and any(packages_cache_dir.iterdir()):
            generate_lock_file(packages_cache_dir, lock_path)

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
    