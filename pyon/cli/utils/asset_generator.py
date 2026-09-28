import json
from pathlib import Path
from typing import Any


def generate_production_assets(
        project_root: Path, 
        dist_dir: Path, 
        config: dict, 
        deps: Any, 
        lock_pkgs: dict, 
        include_pyodide: bool
):
    project_name = config.get("project", {}).get("name", "PyOn-Py App")

    # config = get_pyon_config(project_root)
    # project_name = config.get("project", {}).get("name", "PyOn-Py App")
    
    # deps = get_dependencies(project_root)
    # lock_pkgs = get_lock_packages(project_root)
    
    # Load env
    env_vars = {}
    build_config = config.get("build", {})
    env_file_name = build_config.get("env", {}).get("file", ".env.production")
    env_path = project_root / env_file_name
    
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key.startswith("PYON_"):
                env_vars[key] = value

    pyodide_version = config.get("dev", {}).get("pyodide_version", "314.0.2")
    pyodide_url = "/pyodide/pyodide.js" if include_pyodide else f"https://cdn.jsdelivr.net/pyodide/v{pyodide_version}/full/pyodide.js"

    loader_js = f"""\
// loader.js — PRODUCTION BUILD
const PYODIDE_URL = "{pyodide_url}";
const PACKAGES = {json.dumps(deps)};
const LOCK_PACKAGES = {json.dumps(lock_pkgs)};
const PYON_ENV = {json.dumps(env_vars)};

async function loadScript(url) {{
    return new Promise((resolve, reject) => {{
        if (document.querySelector(`script[src="${{url}}"]`)) {{
            resolve();
            return;
        }}
        const script = document.createElement("script");
        script.src = url;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    }});
}}

async function injectEnv(pyodide) {{
    const env_str = JSON.stringify(PYON_ENV);
    await pyodide.runPythonAsync(`
import json as _json
import sys as _sys

_injected_env_data = ${{env_str}}

try:
    import pyon.env as _pyon_env_module
    _pyon_env_module._env_data.update(_injected_env_data)
except ImportError:
    pass
`);
}}

async function initPyOnPy() {{
    try {{
        console.log("[PyOnPy] Loading Pyodide...");
        await loadScript(PYODIDE_URL);
        window.__pyodide = await loadPyodide();
        window.__pyodide.runPython('import os; os.environ["PYON_ENV"] = "production"');
        window.__pyodide.runPython('import sys; sys.path.insert(0, "/")');

        console.log("[PyOnPy] Installing dependencies...");
        await window.__pyodide.loadPackage("micropip");
        const micropip = window.__pyodide.pyimport("micropip");

        for (const [name, filename] of Object.entries(LOCK_PACKAGES)) {{
            await micropip.install(`/packages/${{filename}}`);
        }}
        await micropip.install(["typing-extensions"].concat(PACKAGES));

        console.log("[PyOnPy] Loading application bundle...");
        const response = await fetch("/app.zip");
        const buffer = await response.arrayBuffer();
        window.__pyodide.unpackArchive(buffer, "zip", {{ extractDir: "/" }});

        await injectEnv(window.__pyodide);

        console.log("[PyOnPy] Rendering...");
        const appEl = document.getElementById("app");
        if (appEl) appEl.innerHTML = "";

        await window.__pyodide.runPythonAsync(`
from app import start
start()
`);
    }} catch (err) {{
        console.error("[PyOnPy] Error:", err);
    }}
}}

initPyOnPy();
"""

    # Check if a custom index.html exists in project root or src
    custom_index = project_root / "index.html"
    if not custom_index.exists():
        custom_index = project_root / "src" / "index.html"

    if custom_index.exists():
        index_html = custom_index.read_text()
        # Ensure it has loader.js
        if "loader.js" not in index_html:
            index_html = index_html.replace("</body>", '    <script src="/loader.js"></script>\n</body>')
        if "<div id=\"pyon-py-status\">Loading...</div>" in index_html:
            index_html = index_html.replace("\n    <div id=\"pyon-py-status\">Loading...</div>", '')
    else:
        # Fallback if the user has absolutely no index.html (highly unlikely if they use dev server)
        if (project_root / "src" / "static" / "css" / "output.css").exists():
            css_link = '<link href="/src/static/css/output.css" rel="stylesheet">'
        elif (project_root / "static" / "css" / "output.css").exists():
            css_link = '<link href="/static/css/output.css" rel="stylesheet">'
        else:
            css_link = ''

        index_html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name}</title>
    {css_link}
</head>
<body>
    <div id="app"></div>
    <script src="/loader.js"></script>
</body>
</html>
"""

    (dist_dir / "loader.js").write_text(loader_js)
    (dist_dir / "index.html").write_text(index_html)
