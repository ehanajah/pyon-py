from pathlib import Path

import tomlkit


def get_pyon_toml_path():
    return Path.cwd() / "pyon.toml"

def read_pyon_toml():
    path = get_pyon_toml_path()
    if not path.exists():
        raise FileNotFoundError(f"pyon.toml not found in {path}. Run 'pyon init' to create a new pyon.toml file.")
    return tomlkit.parse(path.read_text("utf-8"))

def write_pyon_toml(doc: tomlkit.TOMLDocument):
    path = get_pyon_toml_path()
    path.write_text(tomlkit.dumps(doc), "utf-8")

def add_dependency(package: str, version: str, is_dev: bool = False):
    doc = read_pyon_toml()
    section = "dev-dependencies" if is_dev else "dependencies"

    if section not in doc:
        doc[section] = tomlkit.table()
    if "packages" not in doc[section]:
        doc[section]["packages"] = tomlkit.array()

    packages_array = doc[section]["packages"]
    new_entry = f"{package}>={version}" if version else package

    to_remove = [i for i, p in enumerate(packages_array) if p == package or p.startswith((f"{package}>=", f"{package}=="))]
    for i in reversed(to_remove):
        del packages_array[i]

    packages_array.append(new_entry)
    write_pyon_toml(doc)

def remove_dependency(package: str):
    doc = read_pyon_toml()
    removed = False

    for section in ["dependencies", "dev-dependencies"]:
        if section in doc and "packages" in doc[section]:
            arr = doc[section]["packages"]
            to_remove = [i for i, p in enumerate(arr) if p == package or p.startswith((f"{package}>=", f"{package}=="))]
            for i in reversed(to_remove):
                del arr[i]
                removed = True

    if removed:
        write_pyon_toml(doc)
    return removed
