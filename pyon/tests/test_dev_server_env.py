import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from pyon.dev_server.server import _load_env

def test_load_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        env_file = tmp_path / ".env"
        env_file.write_text(
            "PYON_API_URL=http://localhost:8000\n"
            "PYON_DEBUG=true\n"
            "SECRET_KEY=supersecret\n"
            "# COMMENT=test\n"
            "INVALID_LINE\n"
            "PYON_QUOTED=\"quoted_value\"\n"
            "PYON_SINGLE_QUOTED='single_quoted'\n"
        )
        
        # Patch PROJECT_ROOT in server.py
        with patch("pyon.dev_server.server.PROJECT_ROOT", tmp_path):
            env_vars = _load_env(".env")
            
            assert "PYON_API_URL" in env_vars
            assert env_vars["PYON_API_URL"] == "http://localhost:8000"
            
            assert "PYON_DEBUG" in env_vars
            assert env_vars["PYON_DEBUG"] == "true"
            
            assert "PYON_QUOTED" in env_vars
            assert env_vars["PYON_QUOTED"] == "quoted_value"
            
            assert "PYON_SINGLE_QUOTED" in env_vars
            assert env_vars["PYON_SINGLE_QUOTED"] == "single_quoted"
            
            # Non-PYON prefixed should not be loaded
            assert "SECRET_KEY" not in env_vars
            assert "COMMENT" not in env_vars
            assert "INVALID_LINE" not in env_vars
