import importlib.metadata
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import click

from .utils.lock_utils import generate_lock_file
from .utils.toml_utils import add_dependency, get_pyon_toml_path, read_pyon_toml
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

    doc = read_pyon_toml()
    pyodide_version = doc.get("dev", {}).get("pyodide_version", "314.0.6")

    packages_to_install = []
    
    # WASM compatibility check
    if not dev:
        for pkg in packages:
            click.echo(f"Checking WASM compatibility for {pkg}...")
            status, msg, version = check_wasm_compatible(pkg, pyodide_version)
            pkg_req = f"{pkg}=={version}" if version else pkg
            packages_to_install.append(pkg_req)

            if status == WasmStatus.BUILTIN:
                click.secho(msg, fg="green")
                
                if doc.get("dev", {}).get("local_pyodide", False):
                    import json
                    import urllib.request
                    lock_file = Path.cwd() / "pyodide_cache" / "pyodide-lock.json"
                    if lock_file.exists():
                        try:
                            with open(lock_file, "r") as f:
                                lock_data = json.load(f)
                            packages_dict = lock_data.get("packages", {})
                            
                            resolved = set()
                            queue = [pkg.lower()]
                            while queue:
                                p = queue.pop(0)
                                if p not in resolved and p in packages_dict:
                                    resolved.add(p)
                                    queue.extend(packages_dict[p].get("depends", []))
                                    
                            click.echo(f"Syncing {len(resolved)} wheels for '{pkg}' to local pyodide_cache...")
                            for p in resolved:
                                filename = packages_dict[p]["file_name"]
                                wheel_path = Path.cwd() / "pyodide_cache" / filename
                                if not wheel_path.exists():
                                    wheel_url = f"https://cdn.jsdelivr.net/pyodide/v{pyodide_version}/full/{filename}"
                                    sys.stdout.write(f"  Downloading {filename}...\n")
                                    sys.stdout.flush()
                                    urllib.request.urlretrieve(wheel_url, wheel_path)
                        except Exception as e:
                            click.secho(f"Warning: Failed to sync builtin wheel to pyodide_cache: {e}", fg="yellow")
                
                # Skip pip download for builtin packages, Pyodide will handle them
                continue

            elif status == WasmStatus.INCOMPATIBLE:
                click.secho(msg, fg="red", bold=True)
                click.confirm(f"'{pkg}' may not work in WASM/browser environments. Do you want to continue adding it?", abort=True)

            elif status == WasmStatus.UNKNOWN:
                click.secho(msg, fg="yellow")

            if status == WasmStatus.PURE_PYTHON or status == WasmStatus.UNKNOWN:
                click.echo(f"Testing download Pure Python wheels for '{pkg_req}' with dependencies...")

                with tempfile.TemporaryDirectory() as temp_dir:
                    cmd = [
                        sys.executable, "-m", "pip", "download",                                                               
                        "--only-binary=:all:",
                        "--platform", "any",
                        "--python-version", "3.11",
                        "-d", temp_dir,
                        pkg_req 
                    ]

                    result = subprocess.run(cmd, check=False, capture_output=True, text=True)

                    if result.returncode != 0:
                        click.secho(f"Failed: '{pkg_req}' or its transitive dependencies depend on C extension (has no pure python wheel).", fg="red")
                        click.echo("Use --dev argument if only for development usage.")
                        sys.exit(1)

                    packages_cache_dir.mkdir(exist_ok=True)
                    for wheel_file in Path(temp_dir).glob("*.whl"):
                        target_file = packages_cache_dir / wheel_file.name
                        if not target_file.exists():
                            shutil.copy(wheel_file, target_file)

                    click.secho(f"'{pkg_req}' is validated and cached at {packages_cache_dir}", fg="green")

        if packages_cache_dir.exists() and any(packages_cache_dir.iterdir()):
            generate_lock_file(packages_cache_dir, lock_path)
    else:
        packages_to_install = list(packages)

    # Install packages using pip
    click.echo(f"Installing packages: {', '.join(packages_to_install)}...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", *packages_to_install], check=False)

    if result.returncode != 0:
        click.secho("Failed to install packages via pip", fg="red", err=True)
        sys.exit(1)

    for pkg in packages:
        version = get_installed_version(pkg)
        add_dependency(pkg, version, is_dev=dev)
        click.secho(f" Successfully added {pkg}=={version} to {'dev-dependencies' if dev else 'dependencies'} in pyon.toml", fg="blue")
    