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

    # Prune packages_cache and pyon.lock
    import shutil
    import tempfile
    from pathlib import Path

    from .utils.lock_utils import generate_lock_file
    from .utils.toml_utils import read_pyon_toml

    doc = read_pyon_toml()
    runtime_packages = doc.get("dependencies", {}).get("packages", [])
    cache_dir = Path.cwd() / "packages_cache"
    lock_path = Path.cwd() / "pyon.lock"

    if cache_dir.exists() or lock_path.exists():
        click.echo("Pruning local cache and pyon.lock...")
        if not runtime_packages:
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
            if lock_path.exists():
                lock_path.unlink()
            click.secho("All runtime dependencies removed. Cache and lock file cleared.", fg="green")
        else:
            with tempfile.TemporaryDirectory() as tmpdir:
                cmd = [
                    sys.executable, "-m", "pip", "download",
                    "--only-binary=:all:",
                    "--platform", "any",
                    "--python-version", "3.11",
                    "-d", tmpdir,
                ] + list(runtime_packages)
                
                result = subprocess.run(cmd, check=False, capture_output=True, text=True)
                if result.returncode == 0:
                    if cache_dir.exists():
                        shutil.rmtree(cache_dir)
                    shutil.copytree(tmpdir, cache_dir)
                    generate_lock_file(cache_dir, lock_path)
                    click.secho("Local cache and pyon.lock successfully updated.", fg="green")
                else:
                    click.secho("Warning: Failed to prune cache properly. You may need to run 'pyon download'.", fg="yellow")
            