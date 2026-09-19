import json
import os
import tempfile
import urllib.error
import urllib.request
from unittest.mock import patch, MagicMock

from pyon.cli.utils.wasm_check import check_wasm_compatible, WasmStatus

def test_wasm_check_builtin():
    # Mock urllib.request.urlopen to return pyodide lock json
    mock_pyodide_lock = {
        "packages": {
            "pydantic": {
                "version": "2.10.3"
            }
        }
    }
    
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_pyodide_lock).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            with patch("urllib.request.urlopen", return_value=mock_response):
                status, msg, version = check_wasm_compatible("pydantic", "314.0.6")
                
                assert status == WasmStatus.BUILTIN
                assert version == "2.10.3"
                assert "built-in package" in msg
        finally:
            os.chdir(original_cwd)

def test_wasm_check_pure_python():
    mock_pypi_data = {
        "info": {"version": "1.2.3"},
        "releases": {
            "1.2.3": [
                {"filename": "somepkg-1.2.3.tar.gz"},
                {"filename": "somepkg-1.2.3-py3-none-any.whl"}
            ]
        }
    }
    
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_pypi_data).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            def urlopen_side_effect(req, *args, **kwargs):
                if "pyodide-lock" in req.full_url:
                    raise urllib.error.URLError("Not found")
                return mock_response
                
            with patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
                status, msg, version = check_wasm_compatible("somepkg", "314.0.6")
                
                assert status == WasmStatus.PURE_PYTHON
                assert version == "1.2.3"
                assert "pure Python package" in msg
        finally:
            os.chdir(original_cwd)

def test_wasm_check_incompatible():
    mock_pypi_data = {
        "info": {"version": "1.0.0"},
        "releases": {
            "1.0.0": [
                {"filename": "cpkg-1.0.0-cp311-cp311-manylinux.whl"}
            ]
        }
    }
    
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_pypi_data).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            def urlopen_side_effect(req, *args, **kwargs):
                if "pyodide-lock" in req.full_url:
                    raise urllib.error.URLError("Not found")
                return mock_response
                
            with patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
                status, msg, version = check_wasm_compatible("cpkg", "314.0.6")
                
                assert status == WasmStatus.INCOMPATIBLE
                assert version == ""
                assert "C extensions" in msg
        finally:
            os.chdir(original_cwd)
