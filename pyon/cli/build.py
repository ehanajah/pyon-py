import py_compile
import shutil
import tomllib
import zipfile
from pathlib import Path

import click

from .utils.asset_generator import generate_production_assets
from .utils.file_collector import collect_project_files


def get_pyon_config(project_root: Path):
    toml_path = project_root / "pyon.toml"
    if not toml_path.exists():
        return {}
    try:
        with open(toml_path, "rb") as f:
            return tomllib.load(f)
    except Exception:  # noqa: BLE001
        return {}

def get_dependencies(project_root: Path):
    config = get_pyon_config(project_root)
    return config.get("dependencies", {}).get("packages", [])

def get_lock_packages(project_root: Path):
    lock_path = project_root / "pyon.lock"
    if not lock_path.exists():
        return {}
    try:
        with open(lock_path, "rb") as f:
            data = tomllib.load(f)
            packages = data.get("packages", {})
            return {k: v.get("filename") for k, v in packages.items()}
    except Exception:  # noqa: BLE001
        return {}


@click.command()
@click.option("--outdir", default=None, help="Output directory (default: dist)")
@click.option("--no-bytecode", is_flag=True, default=None, help="Skip .pyc compilation")
@click.option("--include-pyodide", is_flag=True, default=None, help="Copy Pyodide runtime to dist for self-hosting")
def build(outdir: str | None, no_bytecode: bool | None, include_pyodide: bool | None):
    """Build project for production deployment."""
    project_root = Path.cwd()
    config = get_pyon_config(project_root)
    build_config = config.get("build", {})

    # Fallback logic: CLI > TOML > Default
    final_outdir = outdir if outdir is not None else build_config.get("outdir", "dist")
    
    # For booleans: if CLI flag is provided (True), use it. Else check TOML.
    final_no_bytecode = no_bytecode if no_bytecode else build_config.get("no_bytecode", False)
    final_include_pyodide = include_pyodide if include_pyodide else build_config.get("include_pyodide", False)

    with_bytecode = not final_no_bytecode  # 'not no_bytecode' is sometimes confusing me 😅
    dist_dir = project_root / final_outdir
    
    click.echo("\nPyOn-Py Build System")
    click.echo("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 1. Collect files
    click.echo("[1/6] Collecting files...")
    files = collect_project_files(project_root)
    click.echo(f"      Found {len(files)} Python files")

    # Create temporary staging dir
    staging_dir = dist_dir / ".staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    # 2. Bytecode compile
    click.echo("[2/6] Compiling bytecode...")
    compiled_count = 0
    for target_rel, src_abs in files:
        target_path = staging_dir / target_rel
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Always copy the original .py file as fallback
        shutil.copy2(src_abs, target_path)

        if with_bytecode:
            try:
                pyc_path = target_path.with_suffix(".pyc")
                py_compile.compile(str(src_abs), cfile=str(pyc_path), doraise=True)
                compiled_count += 1
            except Exception as e:  # noqa: BLE001
                click.echo(f"      Warning: failed to compile {target_rel}: {e}")

    if with_bytecode:
        click.echo(f"      Compiled {compiled_count} .pyc files")
    else:
        click.echo("      Skipped (.pyc compilation disabled)")

    # 3. Create ZIP bundle
    click.echo("[3/6] Creating bundle...")
    app_zip_path = dist_dir / "app.zip"
    with zipfile.ZipFile(app_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in staging_dir.rglob("*"):
            if file_path.is_file():
                arcname = str(file_path.relative_to(staging_dir))
                zf.write(file_path, arcname)
    
    zip_size = app_zip_path.stat().st_size / 1024
    click.echo(f"      app.zip: {zip_size:.1f} KB")

    # Clean up staging
    shutil.rmtree(staging_dir)

    # 4. Copy Static Assets
    click.echo("[4/6] Copying static assets...")
    static_dirs = [
        (project_root / "src" / "static", dist_dir / "src" / "static"),
        (project_root / "static", dist_dir / "static"),
        (project_root / "public", dist_dir),
    ]
    copied_static = False
    for src, dst in static_dirs:
        if src.exists() and src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
            copied_static = True
    
    if copied_static:
        click.echo("      ✓ Copied static files to dist/")
    else:
        click.echo("      No static assets found.")

    # 5. Generate HTML & Loader
    click.echo("[5/6] Generating production assets...")
    
    # Validation: Fallback to CDN if pyodide_cache is missing
    if final_include_pyodide and not (project_root / "pyodide_cache").exists():
        click.secho(
            "      ! Warning: 'pyodide_cache' not found. "
            "Run 'pyon download pyodide' first to bundle Pyodide.\n"
            "      ! Falling back to CDN for Pyodide URL.", 
            fg="yellow"
        )
        final_include_pyodide = False
            
    generate_production_assets(
        project_root, 
        dist_dir, 
        get_pyon_config(project_root),
        get_dependencies(project_root),
        get_lock_packages(project_root),
        final_include_pyodide
        )
    click.echo("      ✓ index.html")
    click.echo("      ✓ loader.js (production mode)")

    # 6. Copy Dependencies
    click.echo("[6/6] Copying dependencies...")
    copied_deps = 0
    
    cache_dir = project_root / "packages_cache"
    if cache_dir.exists():
        dest_pkg = dist_dir / "packages"
        dest_pkg.mkdir(exist_ok=True)
        for whl in cache_dir.glob("*.whl"):
            shutil.copy2(whl, dest_pkg / whl.name)
            copied_deps += 1

    if final_include_pyodide:
        pyodide_dir = project_root / "pyodide_cache"
        if pyodide_dir.exists():
            shutil.copytree(pyodide_dir, dist_dir / "pyodide", dirs_exist_ok=True)
            click.echo("      ✓ Copied Pyodide runtime")

    click.echo(f"      ✓ {copied_deps} wheel packages → dist/packages/")

    click.echo("\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
    click.echo(f"   Build complete! Output: {final_outdir}/")
    click.echo(f"   Deploy with any static file server:\n     python -m http.server -d {final_outdir}\n")
