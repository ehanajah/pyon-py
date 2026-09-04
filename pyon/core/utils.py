import asyncio
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .component import Component


def dispatch(result: Any, instance: Optional["Component"] = None) -> Any:
    """Dispatches an async result to the event loop.

    This function is a wrapper around ``asyncio.run()`` that catches
    exceptions and calls the ``component_did_catch`` lifecycle method
    if the instance is a Component subclass.

    Args:
        result: The result of an async function.
        instance: The instance that raised the exception.

    Returns:
        The result of the async function, or None if the function is not async.
    """
    if not asyncio.iscoroutine(result):
        return result

    async def _wrapped():
        try:
            await result
        except Exception as e:
            if instance and hasattr(instance, "component_did_catch"):
                from .component import Component
                if type(instance).component_did_catch is not Component.component_did_catch:
                    instance.component_did_catch(e)
                    instance._schedule_update()
                    return

            comp_name = instance.__class__.__name__ if instance else "Unknown"
            print(f"[PyOn-Py Async Error] Unhandled exception in {comp_name}: {e}")

    try:
        loop = asyncio.get_running_loop()
        return loop.create_task(_wrapped())
    except RuntimeError:
        return asyncio.run(_wrapped())
    