from typing import Any

_env_data: dict[str, str] = {}


class PyonEnv:
    """
    Environment variables accessible via `pyon.env.env`.
    Injected from .env file by dev/server.py.
    Only PYON_ prefixed variables are available.

    Example:
        from pyon.env import env
        api_url = env.get("PYON_API_URL", "http://localhost:5000")
    """

    def get(self, key: str, default: Any = None) -> Any:
        return _env_data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        if key not in _env_data:
            raise KeyError(f"Environment variable '{key}' not found")
        return _env_data[key]

    def __contains__(self, key: str) -> bool:
        return key in _env_data

    def all(self) -> dict[str, str]:
        return dict(_env_data)


env = PyonEnv()
