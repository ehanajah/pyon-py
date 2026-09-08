import js


class PyodideAbortController:
    def __init__(self):
        self._controller = js.AbortController.new() # type: ignore

    @property
    def signal(self):
        return self._controller.signal # type: ignore
    
    def abort(self):
        self._controller.abort() # type: ignore

def create_abort_controller():
    return PyodideAbortController()