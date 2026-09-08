from urllib.parse import parse_qsl


def get_query_params(search_str: str) -> dict[str, str]:
    return dict(parse_qsl(search_str.lstrip("?")))

def match_route(defined_path: str, actual_path: str) -> dict[str, str] | None:
    """Match a route path with the current path.

    Args:
        defined_path (str): The route path defined in the router.
        actual_path (str): The current path of the router.

    Returns:
        dict[str, str] | None: A dictionary of parameters extracted from the route path.
            If the route path does not match the current path, returns None.
    """
    if defined_path == actual_path:
        return {}

    def_parts = [p for p in defined_path.split("/") if p]
    act_parts = [p for p in actual_path.split("/") if p]

    if len(def_parts) != len(act_parts):
        return None

    params = {}
    for d, a in zip(def_parts, act_parts):
        if d.startswith(":") and len(d) > 1:
            params[d[1:]] = a
        elif d != a:
            return None
        
    return params
