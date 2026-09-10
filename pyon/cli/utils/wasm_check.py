import json
import urllib.error
import urllib.request
from enum import Enum


class WasmStatus(Enum):
    PURE_PYTHON = "pure"
    BUILTIN = "builtin"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"

def check_wasm_compatible(package_name: str, pyodide_version: str = "314.0.6") -> tuple[WasmStatus, str, str]:
    from pathlib import Path
    repodata = None
    
    local_lock = Path.cwd() / "pyodide_cache" / "pyodide-lock.json"
    if local_lock.exists():
        try:
            with open(local_lock, "r") as f:
                repodata = json.load(f)
        except Exception:  # noqa: BLE001, S110
            pass

    if not repodata:
        try:
            url = f"https://cdn.jsdelivr.net/pyodide/v{pyodide_version}/full/pyodide-lock.json"
            req = urllib.request.Request(url, headers={"User-Agent": "PyOn-Py CLI"})
            with urllib.request.urlopen(req, timeout=5) as response:
                repodata = json.loads(response.read())
        except Exception:  # noqa: BLE001, S110
            pass
            
    if repodata and package_name.lower() in repodata.get("packages", {}):
        version = repodata["packages"][package_name.lower()].get("version", "")
        return WasmStatus.BUILTIN, f"{package_name} is a built-in package in Pyodide {pyodide_version} (version {version})", version

    try:
        url = f"https://pypi.org/pypi/{package_name}/json"
        req = urllib.request.Request(url, headers={"User-Agent": "PyOn-Py CLI"})
        with urllib.request.urlopen(req, timeout=5) as response:
            pypi_data = json.loads(response.read())
            releases = pypi_data.get("releases", {})
            version = pypi_data.get("info", {}).get("version", "")

            if not version or version not in releases:
                return WasmStatus.UNKNOWN, f"Could not determine the latest version of {package_name} from PyPI", ""

            for file_info in releases[version]:
                filename = file_info.get("filename", "")
                if filename.endswith(("-py3-none-any.whl", "-py2.py3-none-any.whl")):
                    return WasmStatus.PURE_PYTHON, f"{package_name} is a pure Python package (wheel: {filename})", version

            return WasmStatus.INCOMPATIBLE, f"{package_name} has C extensions and unavailable at Pyodide {pyodide_version}", ""

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return WasmStatus.UNKNOWN, f"{package_name} not found on PyPI", ""
    except Exception as e:
        return WasmStatus.UNKNOWN, f"Error checking {package_name}: {e!s}", ""

    return WasmStatus.INCOMPATIBLE, f"'{package_name}' is possibly incompatible with WASM/Browser environments", ""
