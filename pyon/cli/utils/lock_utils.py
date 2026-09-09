import datetime
from pathlib import Path

import tomlkit


def generate_lock_file(cache_dir: Path, lock_file_path: Path):
    if not cache_dir.exists():
        return

    doc = tomlkit.document()

    metadata = tomlkit.table()
    metadata.add("generated_at", datetime.datetime.now(datetime.UTC).isoformat())
    metadata.add("python_version", "3.11")
    metadata.add("platform", "any")
    doc.add("metadata", metadata)

    packages = tomlkit.table()

    for wheel_path in sorted(cache_dir.glob("*.whl")):
        filename = wheel_path.name

        parts = filename[:-4].split("-")
        name = parts[0]
        version = parts[1]

        pkg_table = tomlkit.inline_table()
        pkg_table.append("version", version)
        pkg_table.append("filename", filename)
        packages.append(name, pkg_table)

    doc.append("packages", packages)

    lock_file_path.write_text(tomlkit.dumps(doc), "utf-8")
    