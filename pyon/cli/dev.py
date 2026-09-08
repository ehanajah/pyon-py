import asyncio
import sys
from pathlib import Path

import click

# Ensure project root (where pyon is run) is in sys.path
sys.path.insert(0, str(Path.cwd()))

@click.command()
def dev():
    """Run local development server with hot-reload"""
    try:
        from pyon.dev_server import server
    except ImportError as e:
        click.echo(f"Error: {e}")
        click.echo("Failed to import pyon.dev_server.server")
        sys.exit(1)
        
    try:
        asyncio.run(server.main())
    except KeyboardInterrupt:
        click.echo("\nPyOn-Py dev server stopped.")
