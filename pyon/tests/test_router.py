import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# =============================================================================
# Setup Mocks untuk pyon.browser
# =============================================================================
mock_js = MagicMock()
# Setup nilai default untuk js.window.location
mock_js.window.location.pathname = "/"
mock_js.window.location.search = ""

mock_ffi = MagicMock()

mock_browser = type("MockBrowser", (), {"js": mock_js, "ffi": mock_ffi})()
sys.modules["pyon.browser"] = mock_browser

# Import router setelah mock disuntikkan
from pyon.router.utils import get_query_params, match_route
from pyon.router.core import Router
import pyon.router.core
pyon.router.core.js = mock_js

# =============================================================================
# Test Router Utils (Parsing URL)
# =============================================================================
class TestRouterUtils:
    def test_get_query_params_empty(self):
        assert get_query_params("") == {}
        assert get_query_params("?") == {}

    def test_get_query_params_single(self):
        assert get_query_params("?page=2") == {"page": "2"}
        assert get_query_params("search=keyword") == {"search": "keyword"} # Tanpa tanda tanya

    def test_get_query_params_multiple(self):
        result = get_query_params("?q=test&sort=desc&page=1")
        assert result == {"q": "test", "sort": "desc", "page": "1"}

    def test_match_route_exact(self):
        assert match_route("/", "/") == {}
        assert match_route("/about", "/about") == {}
        assert match_route("/users/123", "/users/123") == {}

    def test_match_route_normalization(self):
        # Harus mengabaikan trailing slash atau double slash
        assert match_route("/users/123/", "/users/123") == {}
        assert match_route("/users/123", "users/123/") == {}

    def test_match_route_dynamic(self):
        # Ekstrak satu parameter
        assert match_route("/users/:id", "/users/42") == {"id": "42"}
        # Ekstrak banyak parameter
        assert match_route("/users/:id/posts/:post_id", "/users/42/posts/99") == {"id": "42", "post_id": "99"}

    def test_match_route_mismatch(self):
        # Beda path
        assert match_route("/users", "/about") is None
        # Beda panjang segmen
        assert match_route("/users", "/users/123") is None
        # Beda path dinamis tapi awalnya salah
        assert match_route("/admins/:id", "/users/123") is None


# =============================================================================
# Test Core Router (State, History, PubSub)
# =============================================================================
class TestRouterCore:
    def test_router_initialization(self):
        mock_js.window.location.pathname = "/initial"
        mock_js.window.location.search = "?start=1"
        
        router = Router([])
        assert router.current_path == "/initial"
        assert router.current_search == "?start=1"
        assert router.query == {"start": "1"}

    def test_router_push_path_only(self):
        router = Router([])
        subscriber = MagicMock()
        router.subscribe(subscriber)
        
        router.push("/dashboard")
        
        # Mengecek API window.history dipanggil dengan benar
        mock_js.window.history.pushState.assert_called_with(None, "", "/dashboard")
        mock_js.window.scrollTo.assert_called_with(0, 0)
        
        assert router.current_path == "/dashboard"
        assert router.current_search == ""
        assert router.query == {}
        subscriber.assert_called_once_with("/dashboard")

    def test_router_push_with_query(self):
        router = Router([])
        router.push("/users?sort=asc")
        
        mock_js.window.history.pushState.assert_called_with(None, "", "/users?sort=asc")
        assert router.current_path == "/users"
        assert router.current_search == "?sort=asc"
        assert router.query == {"sort": "asc"}

    def test_router_replace(self):
        router = Router([])
        router.replace("/settings?tab=profile")
        
        mock_js.window.history.replaceState.assert_called_with(None, "", "/settings?tab=profile")
        assert router.current_path == "/settings"
        assert router.current_search == "?tab=profile"
        assert router.query == {"tab": "profile"}

    def test_router_is_active(self):
        router = Router([])
        router.push("/about")
        assert router.is_active("/about") is True
        assert router.is_active("/users") is False
