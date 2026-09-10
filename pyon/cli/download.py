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
        import json
        import shutil
        import tarfile
        import tempfile
        import urllib.request

        pyodide_version = doc.get("dev", {}).get("pyodide_version", "314.0.6")
        pyodide_release = doc.get("dev", {}).get("pyodide_release", "core")
        pyodide_filename = f"pyodide-core-{pyodide_version}.tar.bz2" if pyodide_release == "core" else f"pyodide-{pyodide_version}.tar.bz2"
        pyodide_url = f"https://github.com/pyodide/pyodide/releases/download/{pyodide_version}/{pyodide_filename}"
        cache_dir = Path.cwd() / "pyodide_cache"

        def download_progress(count, block_size, total_size):
            if total_size > 0:
                percent = int(count * block_size * 100 / total_size)
                percent = min(percent, 100)
                sys.stdout.write(f"\rDownloading Pyodide {pyodide_version}: {percent}%")
                sys.stdout.flush()

        click.echo("\nFetching Pyodide runtime from GitHub...")
        with tempfile.TemporaryDirectory() as tmpdir:
            tar_path = Path(tmpdir) / "pyodide.tar.bz2"
            try:
                urllib.request.urlretrieve(pyodide_url, tar_path, download_progress)
                sys.stdout.write("\n")

                click.echo("Extracting Pyodide...")
                with tarfile.open(tar_path, "r:bz2") as tar:
                    tar.extractall(tmpdir)

                extracted_dir  = Path(tmpdir) / "pyodide"
                if not extracted_dir.exists():
                    click.secho("Failed to locate extracted Pyodide directory.", fg="red", err=True)
                    sys.exit(1)

                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                shutil.copytree(extracted_dir, cache_dir)

                lock_file = cache_dir / "pyodide-lock.json"
                if lock_file.exists():
                    with open(lock_file, "rb") as f:
                        lock_data = json.load(f)
                    packages = lock_data.get("packages", {})

                    required = {"micropip", "typing-extensions", "packaging"}
                    for pkg in doc.get("dependencies", {}).get("packages", []):
                        if pkg not in required:
                            required.add(pkg)

                    resolved = set()
                    queue = list(required)
                    while queue:
                        pkg = queue.pop(0)
                        if pkg not in resolved and pkg in packages:
                            resolved.add(pkg)
                            depends = packages[pkg].get("depends", [])
                            queue.extend(depends)

                    click.echo(f"Fetching {len(resolved)} required built-in wheels (micropip + dependencies)...")
                    for i, pkg in enumerate(resolved):
                        filename = packages[pkg]["file_name"]
                        wheel_url = f"https://cdn.jsdelivr.net/pyodide/v{pyodide_version}/full/{filename}"
                        wheel_path = cache_dir / filename
                        sys.stdout.write(f"\rDownloading {pkg}: {i+1}/{len(resolved)}")
                        sys.stdout.flush()
                        urllib.request.urlretrieve(wheel_url, wheel_path)
                    sys.stdout.write("\n")

                click.secho(f"Successfully cacheh Pyodide in {cache_dir.name}", fg="green")

                if "dev" not in doc:
                    doc["dev"] = tomlkit.table()
                doc["dev"]["local_pyodide"] = True
                write_pyon_toml(doc)
            except Exception as e:
                click.secho("\nFailed to download Pyodide.", fg="red", err=True)
                click.secho(f"Error: {e}", fg="red", err=True)