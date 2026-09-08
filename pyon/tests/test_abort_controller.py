"""
Test: AbortController — pembatalan HTTP request otomatis saat komponen unmount.

Menguji:
- ContextVar current_component di-set saat dispatch async
- _get_abort_signal() lazy-create AbortController
- _invoke_on_unmount() memanggil abort()
- HTTP client menyisipkan signal otomatis ketika ada current_component
- HTTP client TIDAK menyisipkan signal ketika tidak ada current_component
- asyncio.CancelledError dilempar saat AbortError terjadi

Run:
    python pyon/tests/test_abort_controller.py
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ============================================================================
# Mock bridge layer
# ============================================================================

class MockElement:
    def __init__(self, tag="div"):
        self.tag = tag
        self.className = ""
        self.textContent = ""
        self.attributes = {}
        self.child_nodes = []
        self.parent = None
        self.style = MagicMock()
        self._event_listeners = {}

    @property
    def childNodes(self):
        return self.child_nodes

    @property
    def children(self):
        return [c for c in self.child_nodes if isinstance(c, MockElement)]

    def appendChild(self, child):
        self.child_nodes.append(child)
        if isinstance(child, MockElement):
            child.parent = self
        return child

    def insertBefore(self, new_child, ref_child):
        if ref_child in self.child_nodes:
            idx = self.child_nodes.index(ref_child)
            self.child_nodes.insert(idx, new_child)
        else:
            self.appendChild(new_child)
        return new_child

    def remove(self):
        if self.parent:
            self.parent.child_nodes.remove(self)

    def replaceWith(self, new_el):
        if self.parent:
            idx = self.parent.child_nodes.index(self)
            self.parent.child_nodes[idx] = new_el
            new_el.parent = self.parent

    def setAttribute(self, key, val):
        self.attributes[key] = val

    def removeAttribute(self, key):
        self.attributes.pop(key, None)

    def addEventListener(self, event, handler):
        self._event_listeners.setdefault(event, []).append(handler)


class MockTextNode:
    def __init__(self, text):
        self.textContent = text
        self.parent = None


class MockDocument:
    def __init__(self):
        self._elements = {}
        self._app_container = MockElement("div")
        self._elements["#app"] = self._app_container

    def querySelector(self, selector):
        return self._elements.get(selector)

    def createElement(self, tag):
        return MockElement(tag)

    def createTextNode(self, text):
        return MockTextNode(text)


class MockProxy:
    def __init__(self, fn):
        self._fn = fn
        self._destroyed = False

    def __call__(self, *args, **kwargs):
        return self._fn(*args, **kwargs)

    def destroy(self):
        self._destroyed = True


mock_document = MockDocument()
mock_js = MagicMock()
mock_js.document = mock_document
mock_js.queueMicrotask = lambda proxy: proxy()

mock_pyodide_ffi = MagicMock()
mock_pyodide_ffi.create_proxy = lambda fn: MockProxy(fn)

# Mock the full pyon.browser module hierarchy
import types

mock_browser = types.ModuleType("pyon.browser")
mock_browser.js = mock_js
mock_browser.ffi = mock_pyodide_ffi

# Default mock fetch (will be patched in individual tests)
async def _default_mock_fetch(url, method="GET", **kwargs):
    raise NotImplementedError("Use patch to override fetch in tests")

mock_browser.fetch = _default_mock_fetch

mock_protocol = types.ModuleType("pyon.browser._protocol")
mock_protocol_http = types.ModuleType("pyon.browser._protocol.http")

class _MockAbortControllerProtocol:
    signal = None
    def abort(self): pass

class _MockFetchResponse:
    ok: bool
    status: int
    status_text: str
    url: str
    headers: dict

mock_protocol_http.AbortController = _MockAbortControllerProtocol
mock_protocol_http.FetchResponse = _MockFetchResponse
mock_protocol.FetchResponse = _MockFetchResponse
mock_browser.FetchResponse = _MockFetchResponse

mock_impl = types.ModuleType("pyon.browser.impl")
mock_impl.create_abort_controller = lambda: MockAbortController()

sys.modules["pyon.browser"] = mock_browser
sys.modules["pyon.browser._protocol"] = mock_protocol
sys.modules["pyon.browser._protocol.http"] = mock_protocol_http
sys.modules["pyon.browser.impl"] = mock_impl

from pyon.core import Component, VNode, h, dispatch
from pyon.core.utils import current_component

# ============================================================================
# Test helper
# ============================================================================

results: list[tuple[str, bool, str]] = []


def report(name: str, passed: bool, detail: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append((name, passed, detail))
    print(f"  {status}  {name}" + (f" — {detail}" if detail else ""))


# ============================================================================
# Mock AbortController
# ============================================================================

class MockAbortSignal:
    """Simulasi AbortSignal browser."""
    def __init__(self):
        self.aborted = False


class MockAbortController:
    """Simulasi AbortController browser."""
    def __init__(self):
        self.signal = MockAbortSignal()
        self._aborted = False

    def abort(self):
        self._aborted = True
        self.signal.aborted = True


def mock_create_abort_controller():
    return MockAbortController()


# ============================================================================
# MAIN TEST
# ============================================================================

def run_tests():
    print("=" * 70)
    print("PyOn-Py Test — AbortController & HTTP Request Cancellation")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. _get_abort_signal() LAZY-CREATES ABORT CONTROLLER
    # ------------------------------------------------------------------
    print("\n▶ Test 1: _get_abort_signal() lazy-creates AbortController")

    try:
        comp = Component.__new__(Component)
        comp.__init__()

        report(
            "_abort_controller awalnya None",
            comp._abort_controller is None,
        )

        # Patch create_abort_controller
        with patch("pyon.browser.impl.create_abort_controller", mock_create_abort_controller):
            signal = comp._get_abort_signal()

        report(
            "_abort_controller ter-create setelah _get_abort_signal()",
            comp._abort_controller is not None,
        )
        report(
            "signal yang dikembalikan valid",
            signal is not None and hasattr(signal, "aborted"),
        )
        report(
            "signal belum aborted",
            signal.aborted is False,
        )

        # Panggil kedua kali → harus reuse controller yang sama
        controller_first = comp._abort_controller
        with patch("pyon.browser.impl.create_abort_controller", mock_create_abort_controller):
            signal2 = comp._get_abort_signal()
        report(
            "_get_abort_signal() kedua kali → reuse controller",
            comp._abort_controller is controller_first,
        )

    except Exception as e:
        report("_get_abort_signal()", False, f"Exception: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 2. _invoke_on_unmount() CALLS abort()
    # ------------------------------------------------------------------
    print("\n▶ Test 2: _invoke_on_unmount() memanggil abort()")

    try:
        comp = Component.__new__(Component)
        comp.__init__()
        comp._mounted = True

        # Set up a mock abort controller
        controller = MockAbortController()
        comp._abort_controller = controller

        report(
            "Sebelum unmount: controller belum aborted",
            controller._aborted is False,
        )

        comp._invoke_on_unmount()

        report(
            "Setelah unmount: controller.abort() dipanggil",
            controller._aborted is True,
        )
        report(
            "Setelah unmount: signal.aborted = True",
            controller.signal.aborted is True,
        )

    except Exception as e:
        report("_invoke_on_unmount()", False, f"Exception: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 3. _invoke_on_unmount() TANPA ABORT CONTROLLER → AMAN
    # ------------------------------------------------------------------
    print("\n▶ Test 3: _invoke_on_unmount() tanpa abort controller (aman)")

    try:
        comp = Component.__new__(Component)
        comp.__init__()
        comp._mounted = True

        # Tidak ada abort controller → harus tetap aman
        comp._invoke_on_unmount()
        report(
            "Unmount tanpa abort controller → tidak error",
            True,
        )

    except Exception as e:
        report("Unmount tanpa controller", False, f"Exception: {e}")

    # ------------------------------------------------------------------
    # 4. ContextVar DI-SET SAAT DISPATCH ASYNC
    # ------------------------------------------------------------------
    print("\n▶ Test 4: ContextVar current_component di-set saat dispatch")

    try:
        comp = Component.__new__(Component)
        comp.__init__()

        captured_component = None

        async def capture_context():
            nonlocal captured_component
            captured_component = current_component.get()

        # dispatch secara internal mengelola event loop sendiri 
        # (asyncio.run jika tidak ada loop, create_task jika ada)
        dispatch(capture_context(), instance=comp)

        report(
            "current_component di-set ke instance saat async dispatch",
            captured_component is comp,
            f"captured: {captured_component}, expected: {comp}",
        )

    except Exception as e:
        report("ContextVar dispatch", False, f"Exception: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 5. ContextVar DI-RESET SETELAH DISPATCH SELESAI
    # ------------------------------------------------------------------
    print("\n▶ Test 5: ContextVar di-reset setelah dispatch selesai")

    try:
        report(
            "current_component kembali None setelah dispatch",
            current_component.get() is None,
            f"value: {current_component.get()}",
        )

    except Exception as e:
        report("ContextVar reset", False, f"Exception: {e}")

    # ------------------------------------------------------------------
    # 6. ContextVar TANPA INSTANCE → DEFAULT None
    # ------------------------------------------------------------------
    print("\n▶ Test 6: ContextVar tanpa instance → default None")

    try:
        captured = None

        async def capture_without_instance():
            nonlocal captured
            captured = current_component.get()

        dispatch(capture_without_instance(), instance=None)

        report(
            "current_component = None saat dispatch tanpa instance",
            captured is None,
            f"captured: {captured}",
        )

    except Exception as e:
        report("ContextVar tanpa instance", False, f"Exception: {e}")

    # ------------------------------------------------------------------
    # 7. HTTP CLIENT MENYISIPKAN SIGNAL OTOMATIS
    # ------------------------------------------------------------------
    print("\n▶ Test 7: HTTP client menyisipkan signal saat ada current_component")

    try:
        comp = Component.__new__(Component)
        comp.__init__()

        controller = MockAbortController()
        comp._abort_controller = controller

        captured_kwargs = {}

        async def mock_fetch(url, method="GET", **kwargs):
            captured_kwargs.update(kwargs)
            # Return mock response
            mock_resp = MagicMock()
            mock_resp.ok = True
            mock_resp.status = 200
            mock_resp.status_text = "OK"
            mock_resp.url = url
            mock_resp.headers = {}
            mock_resp.json = AsyncMock(return_value={})
            mock_resp.string = AsyncMock(return_value="")
            return mock_resp

        async def test_signal_injection():
            token = current_component.set(comp)
            try:
                from pyon.http.client import request
                with patch("pyon.http.client.fetch", mock_fetch):
                    await request("GET", "https://api.example.com/data")
            finally:
                current_component.reset(token)

        asyncio.run(test_signal_injection())

        report(
            "signal disertakan dalam kwargs fetch",
            "signal" in captured_kwargs,
            f"kwargs keys: {list(captured_kwargs.keys())}",
        )
        report(
            "signal berasal dari abort controller komponen",
            captured_kwargs.get("signal") is controller.signal,
        )

    except Exception as e:
        report("HTTP signal injection", False, f"Exception: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 8. HTTP CLIENT TANPA CURRENT_COMPONENT → TANPA SIGNAL
    # ------------------------------------------------------------------
    print("\n▶ Test 8: HTTP client tanpa current_component → tanpa signal")

    try:
        captured_kwargs = {}

        async def mock_fetch_no_signal(url, method="GET", **kwargs):
            captured_kwargs.update(kwargs)
            mock_resp = MagicMock()
            mock_resp.ok = True
            mock_resp.status = 200
            mock_resp.status_text = "OK"
            mock_resp.url = url
            mock_resp.headers = {}
            mock_resp.json = AsyncMock(return_value={})
            mock_resp.string = AsyncMock(return_value="")
            return mock_resp

        async def test_no_signal():
            # Pastikan tidak ada current_component
            assert current_component.get() is None
            from pyon.http.client import request
            with patch("pyon.http.client.fetch", mock_fetch_no_signal):
                await request("GET", "https://api.example.com/data")

        asyncio.run(test_no_signal())

        report(
            "signal TIDAK disertakan saat tanpa current_component",
            "signal" not in captured_kwargs,
            f"kwargs keys: {list(captured_kwargs.keys())}",
        )

    except Exception as e:
        report("HTTP tanpa signal", False, f"Exception: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 9. ABORT ERROR → asyncio.CancelledError
    # ------------------------------------------------------------------
    print("\n▶ Test 9: AbortError dikonversi ke asyncio.CancelledError")

    try:
        comp = Component.__new__(Component)
        comp.__init__()

        controller = MockAbortController()
        comp._abort_controller = controller

        async def mock_fetch_abort(url, method="GET", **kwargs):
            raise Exception("AbortError: The operation was aborted")

        caught_error = None

        async def test_abort_error():
            nonlocal caught_error
            token = current_component.set(comp)
            try:
                from pyon.http.client import request
                with patch("pyon.http.client.fetch", mock_fetch_abort):
                    await request("GET", "https://api.example.com/data")
            except asyncio.CancelledError as e:
                caught_error = e
            finally:
                current_component.reset(token)

        asyncio.run(test_abort_error())

        report(
            "AbortError → asyncio.CancelledError",
            caught_error is not None and isinstance(caught_error, asyncio.CancelledError),
            f"error type: {type(caught_error).__name__}" if caught_error else "no error caught",
        )
        report(
            "CancelledError message berisi info abort",
            caught_error is not None and "aborted" in str(caught_error).lower(),
            f"msg: {caught_error}" if caught_error else "",
        )

    except Exception as e:
        report("AbortError conversion", False, f"Exception: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 10. NON-ABORT ERROR → TETAP DILEMPAR SEBAGAI EXCEPTION ASLI
    # ------------------------------------------------------------------
    print("\n▶ Test 10: Non-AbortError tetap dilempar apa adanya")

    try:
        async def mock_fetch_network_error(url, method="GET", **kwargs):
            raise ConnectionError("Network unreachable")

        caught_error = None

        async def test_non_abort():
            nonlocal caught_error
            try:
                from pyon.http.client import request
                with patch("pyon.http.client.fetch", mock_fetch_network_error):
                    await request("GET", "https://api.example.com/data")
            except ConnectionError as e:
                caught_error = e

        asyncio.run(test_non_abort())

        report(
            "ConnectionError tetap dilempar sebagai ConnectionError",
            caught_error is not None and isinstance(caught_error, ConnectionError),
            f"error: {caught_error}",
        )

    except Exception as e:
        report("Non-AbortError propagation", False, f"Exception: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # 11. FULL LIFECYCLE: MOUNT → FETCH → UNMOUNT → ABORT
    # ------------------------------------------------------------------
    print("\n▶ Test 11: Full lifecycle — mount, fetch, unmount, abort")

    try:
        comp = Component.__new__(Component)
        comp.__init__()
        comp._mounted = True

        # Simulasikan: komponen membuat request → mendapat abort controller
        controller = MockAbortController()
        comp._abort_controller = controller

        report(
            "Komponen mounted, controller aktif",
            comp._mounted and not controller._aborted,
        )

        # Simulasikan unmount
        comp._invoke_on_unmount()

        report(
            "Setelah unmount: mounted=False",
            comp._mounted is False,
        )
        report(
            "Setelah unmount: controller.abort() dipanggil",
            controller._aborted is True,
        )
        report(
            "Setelah unmount: signal.aborted=True → fetch akan gagal",
            controller.signal.aborted is True,
        )

    except Exception as e:
        report("Full lifecycle", False, f"Exception: {e}")
        import traceback; traceback.print_exc()

    # ------------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    total = len(results)

    if failed == 0:
        print(f"✅ ALL PASSED: {passed}/{total} tests")
    else:
        print(f"❌ {failed} FAILED, {passed} PASSED out of {total} tests")
        print("\nFailed tests:")
        for name, p, detail in results:
            if not p:
                print(f"  ❌ {name}: {detail}")

    print("=" * 70)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
