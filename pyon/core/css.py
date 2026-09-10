from typing import ClassVar


class CSSManager:
    _registry: ClassVar[dict[str, str]] = {}

    @classmethod
    def register(cls, scope_id: str, css_text: str) -> None:
        cls._registry[scope_id] = css_text

    @classmethod
    def get_all(cls) -> dict[str, str]:
        return cls._registry.copy()
    