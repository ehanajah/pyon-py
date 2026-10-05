import sys
from collections.abc import Sequence
from importlib.abc import Loader, MetaPathFinder
from importlib.util import spec_from_loader
from types import ModuleType


class PyonNetworkLoader(Loader):
    def __init__(self, source: str, fullname: str, is_pkg: bool = False):
        self._source = source
        self._fullname = fullname
        self._is_pkg = is_pkg

    def is_package(self, fullname: str) -> bool:
        return self._is_pkg

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        if self._is_pkg:
            module.__path__ = [self._fullname.replace('.', '/')]
            module.__package__ = self._fullname
        else:
            module.__package__ = self._fullname.rsplit('.', 1)[0] if '.' in self._fullname else ''
        
        if self._source:
            exec(compile(self._source, f"<lazy:{self._fullname}>", 'exec'), module.__dict__)  # noqa: S102


class PyonNetworkFinder(MetaPathFinder):
    BASE_URL = "/pyon_modules/"

    def find_spec(self, fullname: str, path: Sequence[str] | None, target: ModuleType | None = None):
        root_module = fullname.split(".")[0]
        if root_module != "src":
            return None

        from pyon.browser import xhr
        base_path = fullname.replace('.', '/')
        
        url = f"{self.BASE_URL}{base_path}"
        resp = xhr.get(url)
        status = resp.status_code
        
        if status == 406:
            resp_init = xhr.get(f"{url}/__init__.py")
            init_status = resp_init.status_code
            if init_status == 200:
                loader = PyonNetworkLoader(resp_init.text, fullname, is_pkg=True)
                return spec_from_loader(fullname, loader)
            else:
                loader = PyonNetworkLoader("", fullname, is_pkg=True)
                return spec_from_loader(fullname, loader)
                
        resp_mod = xhr.get(f"{url}.py")
        mod_status = resp_mod.status_code
        
        if mod_status == 200:
            loader = PyonNetworkLoader(resp_mod.text, fullname, is_pkg=False)
            return spec_from_loader(fullname, loader)
            
        return None


if sys.platform == "emscripten":
    sys.meta_path.append(PyonNetworkFinder())
        