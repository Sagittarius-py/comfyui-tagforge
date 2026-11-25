from .tagforge_core.nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = "./web"

try:  # routes are optional: nodes must keep working if the server API changes
    from server import PromptServer
    from .tagforge_core.routes import register

    register(PromptServer.instance.routes)
except Exception as e:  # noqa: BLE001
    print(f"[TagForge] HTTP routes disabled: {e}")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
