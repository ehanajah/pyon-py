import json
import urllib.error
import urllib.request
from enum import Enum


class WasmStatus(Enum):
    PURE_PYTHON = "pure"
    BUILTIN = "builtin"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"

def check_wasm_compatible(package_name: str, pyodide_version: str = "314.0.2") -> tuple[WasmStatus, str]:
    try:
        url = f"https://cdn.jsdelivr.net/pyodide/v{pyodide_version}/full/pyodide-lock.json"
        req = urllib.request.Request(url, headers={"User-Agent": "PyOn-Py CLI"})
        with urllib.request.urlopen(req, timeout=5) as response:
            repodata = json.loads(response.read())
            if package_name.lower() in repodata.get("packages", {}):
                return WasmStatus.BUILTIN, f"{package_name} is a built-in package in Pyodide {pyodide_version}"
    except Exception:  # noqa: S110
        pass

    try:
        url = f"https://pypi.org/pypi/{package_name}/json"
        req = urllib.request.Request(url, headers={"User-Agent": "PyOn-Py CLI"})
        with urllib.request.urlopen(req, timeout=5) as response:
            pypi_data = json.loads(response.read())
            releases = pypi_data.get("releases", {})
            version = pypi_data.get("info", {}).get("version", "")

            if not version or version not in releases:
                return WasmStatus.UNKNOWN, f"Could not determine the latest version of {package_name} from PyPI"

            for file_info in releases[version]:
                filename = file_info.get("filename", "")
                if filename.endswith(("-py3-none-any.whl", "-py2.py3-none-any.whl")):
                    return WasmStatus.PURE_PYTHON, f"{package_name} is a pure Python package (wheel: {filename})"

            return WasmStatus.INCOMPATIBLE, f"{package_name} has C extensions and unavailable at Pyodide {pyodide_version}"

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return WasmStatus.UNKNOWN, f"{package_name} not found on PyPI"
    except Exception as e:
        return WasmStatus.UNKNOWN, f"Error checking {package_name}: {str(e)}"

    return WasmStatus.INCOMPATIBLE, f"'{package_name}' is possibly incompatible with WASM/Browser environments"
