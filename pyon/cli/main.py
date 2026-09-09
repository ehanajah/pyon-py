import click

from .add import add
from .dev import dev
from .download import download
from .init import init
from .remove import remove


@click.group()
def cli():
    """PyOn-Py CLI - Python VDOM Framework on Pyodide & WebAssembly"""

cli.add_command(dev)
cli.add_command(init)
cli.add_command(add)
cli.add_command(remove)
cli.add_command(download)

if __name__ == "__main__":
    cli()
