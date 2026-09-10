from pathlib import Path

import click


def create_file(path: Path, content: str):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        click.echo(f"Created: {path}")
    else:
        click.echo(f"Skipped: {path} (already exists)")

@click.command()
def init():
    """PyOn-Py project initialization with minimalist template"""
    cwd = Path.cwd()
    
    # pyon.toml
    pyon_toml = """[project]
name = "my-pyon-app"
version = "0.1.0"

[dependencies]
packages = []

[dev-dependencies]
packages = []

[dev]
pyodide_version = "314.0.6"
pyodide_release = "core"
local_pyodide = false
"""
    create_file(cwd / "pyon.toml", pyon_toml)

    # index.html
    index_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyOn-Py App</title>
    <link rel="stylesheet" href="/src/static/style.css">
</head>
<body>
    <div id="pyon-py-status">Loading...</div>
    <div id="app"></div>
    <script src="/loader.js"></script>
</body>
</html>
"""
    create_file(cwd / "index.html", index_html)

    # app.py
    app_py = """from pyon.core import create_app
from src.App import App


def start():
    app = create_app(App)
    app.mount("#app")


if __name__ == "__main__":
    start()

"""
    create_file(cwd / "app.py", app_py)

    # src/App.py
    src_app_py = """from pyon.core import Component, h
from src.pages.Index import Index


class App(Component):
    def render(self):
        return h("div", {"class": "app-container"}, [h(Index, {})])

"""
    create_file(cwd / "src/App.py", src_app_py)

    # src/static/style.css
    style_css = """body {
    font-family: system-ui, -apple-system, sans-serif;
    background-color: #f5f5f5;
    margin: 0;
    padding: 20px;
}
.card {
    background: white;
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    max-width: 400px;
    margin: 20px auto;
}
"""
    create_file(cwd / "src/static/style.css", style_css)

    # src/pages/Index.py
    src_pages_index_py = """from pyon.core import Component, h
from src.components.Card import Card


class Index(Component):
    def render(self):
        return h(
            "div",
            {},
            [
                h("h1", {"style": "text-align: center;"}, ["Welcome to PyOn-Py"]),
                h(
                    Card,
                    {"title": "Hello World!"},
                    ["This is a minimalistic PyOn-Py template."],
                ),
            ],
        )

"""
    create_file(cwd / "src/pages/Index.py", src_pages_index_py)

    # src/components/Card.py
    src_components_card_py = """from pyon.core import Component, h


class Card(Component):
    def render(self):
        return h(
            "div",
            {"class": "card"},
            [
                h("h2", {}, [self.props.get("title", "Card Title")]),
                h("div", {}, self.props.get("children", [])),
            ],
        )

"""
    create_file(cwd / "src/components/Card.py", src_components_card_py)

    click.echo("\nPyOn-Py project initialized successfully.")
    click.echo("Run `pyon dev` to start local development server.")
