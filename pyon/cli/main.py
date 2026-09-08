import click

from .dev import dev
from .init import init


@click.group()
def cli():
    """PyOn-Py CLI - Python VDOM Framework on Pyodide & WebAssembly"""

cli.add_command(dev)
cli.add_command(init)

if __name__ == "__main__":
    cli()
