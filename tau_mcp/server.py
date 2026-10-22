"""
TAU MCP Server entry point.
Exposes Tel Aviv University (TAU) student portal, course catalog, classroom finder,
and dynamic plugins (including Moodle) to AI assistants via Model Context Protocol (MCP).
Supports stdio, SSE, and streamable-http transports.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional, Tuple

# Ensure package root is in sys.path
_pkg_parent = str(Path(__file__).resolve().parent.parent)
if _pkg_parent not in sys.path:
    sys.path.insert(0, _pkg_parent)

# Compatibility across MCP v1 and v2
try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP as MCPServer
    except ImportError:
        raise ImportError("The 'mcp' package is required. Install it with: pip install mcp")

def patch_mcp_list_serialization() -> None:
    """
    Ensures that MCPServer / FastMCP serializes list tool outputs into a single TextContent block.
    Many MCP clients (notably Google Gemini Web) only read content[0], causing tools returning lists
    (e.g., room instances, grades, schedule items) to display only the first item.
    """
    import pydantic_core
    from mcp.types import ContentBlock, TextContent

    modules = []
    try:
        import mcp.server.mcpserver.utilities.func_metadata as fm2
        modules.append(fm2)
    except ImportError:
        pass

    try:
        import mcp.server.fastmcp.utilities.func_metadata as fm1
        modules.append(fm1)
    except ImportError:
        pass

    try:
        import mcp.server.fastmcp.tools.base as tb1
        modules.append(tb1)
    except ImportError:
        pass

    for mod in modules:
        if hasattr(mod, "_convert_to_content"):
            orig = getattr(mod, "_convert_to_content")
            if getattr(orig, "_is_single_block_patched", False):
                continue

            img_cls = getattr(mod, "Image", None)
            aud_cls = getattr(mod, "Audio", None)

            def make_patched(original_func, img_t, aud_t):
                def patched(result):
                    if result is None:
                        return []
                    if isinstance(result, ContentBlock):
                        return [result]
                    if img_t and isinstance(result, img_t):
                        return [result.to_image_content()]
                    if aud_t and isinstance(result, aud_t):
                        return [result.to_audio_content()]
                    if isinstance(result, (list, tuple)):
                        if len(result) == 0:
                            return [TextContent(type="text", text="[]")]
                        special_types = [ContentBlock]
                        if img_t:
                            special_types.append(img_t)
                        if aud_t:
                            special_types.append(aud_t)
                        special_tuple = tuple(special_types)
                        if all(isinstance(x, special_tuple) for x in result):
                            return original_func(result)
                        text = pydantic_core.to_json(result, fallback=str, indent=2).decode("utf-8")
                        return [TextContent(type="text", text=text)]
                    return original_func(result)

                patched._is_single_block_patched = True
                return patched

            setattr(mod, "_convert_to_content", make_patched(orig, img_cls, aud_cls))

# Apply list serialization patch immediately on import
patch_mcp_list_serialization()

def patch_uvicorn_h11() -> None:
    """Increase default incomplete event buffer size to 64KB for large tokens."""
    try:
        import h11
        orig_init = h11.Connection.__init__
        def patched_connection_init(self, our_role, max_incomplete_event_size=65536):
            orig_init(self, our_role, max_incomplete_event_size=max_incomplete_event_size)
        h11.Connection.__init__ = patched_connection_init
    except Exception:
        pass

patch_uvicorn_h11()

import tau_mcp.config as config
from tau_mcp.storage import CacheManager
from tau_mcp.core.auth import TAUAuthManager
from tau_mcp.core.portal import TAUPortalClient
from tau_mcp.core.catalog import TAUCourseCatalogClient
from tau_mcp.core.room_finder import RoomFinder
from tau_mcp.plugin_manager import PluginManager, ensure_moodle_mcp_imported
from tau_mcp.tools import register_all_tau_tools

# Ensure moodle_mcp is mapped dynamically on module import
ensure_moodle_mcp_imported()

logger = logging.getLogger("tau_mcp")

def create_server(profile: Optional[str] = None, include_moodle: bool = True) -> Tuple[Any, Any, Any, Any]:
    """
    Initializes and configures the TAU MCP server.
    Loads core TAU tools and dynamically mounts plugins (such as Moodle).
    """
    prof_name = profile or config.TAU_PROFILE or "default"
    server = MCPServer(
        name=f"tau_mcp_{prof_name}" if prof_name != "default" else "tau_mcp"
    )

    # Automatically annotate tools with MCP read_only_hint / idempotent_hint and wrap exceptions
    orig_add_tool = getattr(server, "add_tool", None)
    if callable(orig_add_tool):
        import functools
        import inspect

        def add_tool_with_annotations(fn: Any, *args: Any, **kwargs: Any) -> Any:
            fn_name = kwargs.get("name") or getattr(fn, "__name__", "")
            if kwargs.get("annotations") is None:
                read_only_prefixes = ("tau_get_", "tau_search_", "moodle_get_", "moodle_search_", "moodle_read_", "moodle_list_")
                destructive_prefixes = ("moodle_delete_", "moodle_clear_", "tau_clear_")
                try:
                    from mcp.types import ToolAnnotations
                    if fn_name.startswith(destructive_prefixes):
                        kwargs["annotations"] = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False)
                    elif fn_name.startswith(read_only_prefixes):
                        kwargs["annotations"] = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True)
                    else:
                        kwargs["annotations"] = ToolAnnotations(read_only_hint=False, destructive_hint=False)
                except Exception:
                    pass

            # Wrap fn to guarantee tool exceptions never crash the SSE stream / connection
            ret_ann = getattr(fn, "__annotations__", {}).get("return", None)

            def make_error_payload(exc: Exception) -> Any:
                err_text = f"Error in {fn_name}: {exc}"
                logger.error(err_text)
                if ret_ann is not None and (ret_ann is dict or "Dict" in str(ret_ann)):
                    return {"error": err_text, "tool": fn_name}
                elif ret_ann is not None and (ret_ann is str or "str" in str(ret_ann)):
                    return err_text
                return [{"error": err_text, "tool": fn_name}]

            if inspect.iscoroutinefunction(fn):
                @functools.wraps(fn)
                async def safe_fn(*a: Any, **kw: Any) -> Any:
                    try:
                        return await fn(*a, **kw)
                    except Exception as e:
                        return make_error_payload(e)
            else:
                @functools.wraps(fn)
                def safe_fn(*a: Any, **kw: Any) -> Any:
                    try:
                        return fn(*a, **kw)
                    except Exception as e:
                        return make_error_payload(e)

            return orig_add_tool(safe_fn, *args, **kwargs)

        server.add_tool = add_tool_with_annotations

    # Core components
    cache = CacheManager(profile=prof_name)
    auth_manager = TAUAuthManager(profile=prof_name)
    portal = TAUPortalClient(auth_manager=auth_manager, cache=cache)
    catalog = TAUCourseCatalogClient(cache=cache)
    room_finder = RoomFinder(catalog_client=catalog, portal_client=portal)

    # Dynamic Plugins
    plugin_manager = PluginManager(server=server, config=config, cache=cache)
    loaded_plugins = []
    if include_moodle and config.TAU_INCLUDE_MOODLE:
        loaded_plugins = plugin_manager.load_all_plugins()

    # Register all core TAU tools
    register_all_tau_tools(
        server=server,
        portal=portal,
        catalog=catalog,
        room_finder=room_finder,
        cache=cache,
        plugin_names=loaded_plugins
    )

    # Register TAU Resources
    @server.resource("tau://schedule")
    def get_schedule_resource() -> str:
        """Authenticated student's upcoming class schedule and classrooms."""
        schedule = portal.get_personal_schedule()
        return json.dumps([s.__dict__ for s in schedule], indent=2, ensure_ascii=False)

    @server.resource("tau://grades")
    def get_grades_resource() -> str:
        """Authenticated student's course grades and credit history."""
        grades = portal.get_grades()
        return json.dumps([g.__dict__ for g in grades], indent=2, ensure_ascii=False)

    @server.resource("tau://gpa")
    def get_gpa_resource() -> str:
        """Cumulative GPA and degree credit summary."""
        gpa = portal.get_gpa_stats()
        return json.dumps([s.__dict__ for s in gpa], indent=2, ensure_ascii=False)

    @server.resource("tau://messages")
    def get_messages_resource() -> str:
        """Student messages and classroom change announcements."""
        messages = portal.get_messages(include_earlier=True)
        return json.dumps([m.__dict__ for m in messages], indent=2, ensure_ascii=False)

    @server.resource("tau://cache")
    def get_cache_resource() -> str:
        """In-memory cache statistics and entry lifetimes."""
        stats = cache.get_stats()
        return json.dumps(stats, indent=2, ensure_ascii=False)

    # Register TAU Prompts
    @server.prompt()
    def daily_briefing() -> str:
        """Daily academic briefing: schedule, classrooms, messages, and Moodle deadlines."""
        return (
            "You are an academic assistant for a student at Tel Aviv University. "
            "Please call `tau_get_my_schedule` to see what classes I have today, check their classrooms and buildings, "
            "check `tau_get_my_messages` for any one-time room changes, "
            "and if Moodle tools are available, call `moodle_get_upcoming_assignments` to summarize my pending deadlines."
        )

    @server.prompt()
    def find_class_room(course_name_or_number: str, hour: str = "") -> str:
        """Find the classroom for a course and check for any change announcements."""
        return (
            f"Please call `tau_get_course_room` for course '{course_name_or_number}' at hour '{hour}'. "
            "Report the building, room number, lecturer, and check if there are any active room change announcements."
        )

    return server, portal, catalog, room_finder


def run_streamable_http_server(server: Any, host: str = "0.0.0.0", port: int = 8000) -> None:
    """Runs tau-mcp with Starlette Streamable HTTP transport, OAuth 2.1 support, and /health endpoint."""
    import uvicorn
    import anyio
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse, RedirectResponse
    from starlette.routing import Route, Mount
    from starlette.middleware.cors import CORSMiddleware
    from contextlib import AsyncExitStack, asynccontextmanager

    try:
        from mcp.server.transport_security import TransportSecuritySettings
    except ImportError:
        try:
            from mcp.server.streamable_http import TransportSecuritySettings
        except ImportError:
            TransportSecuritySettings = None

    try:
        from mcp.server.streamable_http_manager import StreamableHTTPASGIApp
    except ImportError:
        try:
            from mcp.server.streamable_http import StreamableHTTPASGIApp
        except ImportError:
            StreamableHTTPASGIApp = None

    security = None
    if TransportSecuritySettings:
        try:
            security = TransportSecuritySettings(
                enable_dns_rebinding_protection=False,
                allowed_hosts=["*"],
                allowed_origins=["*"]
            )
        except Exception:
            try:
                security = TransportSecuritySettings(
                    allowed_origins=["*"],
                    allowed_hosts=["*"]
                )
            except Exception:
                pass

    async def root_info(req: Any) -> JSONResponse:
        return JSONResponse({
            "service": "tau-mcp-unified",
            "transport": "streamable-http",
            "status": "online",
            "endpoints": {"mcp": "/mcp", "health": "/health", "authorize": "/authorize"}
        })

    custom_routes = [
        Route("/mcp", endpoint=root_info, methods=["GET", "HEAD"]),
        Route("/", endpoint=root_info, methods=["GET", "HEAD"]),
    ]

    mcp_app = server._lowlevel_server.streamable_http_app(
        streamable_http_path="/mcp",
        host=host,
        transport_security=security,
        custom_starlette_routes=custom_routes,
    )

    async def health(req: Any) -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "service": "tau-mcp-unified",
            "transport": "streamable-http"
        })

    routes = [
        Route("/health", health, methods=["GET"]),
    ]

    # Mount OAuth 2.1 endpoints if moodle_mcp is available
    token_manager = None
    try:
        from moodle_mcp.oauth import TokenManager, create_oauth_routes, BearerAuthMiddleware
        token_manager = TokenManager()
        for r in create_oauth_routes(token_manager):
            routes.append(r)
        logger.info("Mounted OAuth 2.1 metadata, authorize, and token routes.")
    except Exception as e:
        logger.debug(f"OAuth 2.1 routes not mounted: {e}")

    session_mgr = getattr(server._lowlevel_server, "_session_manager", None)
    if session_mgr and StreamableHTTPASGIApp:
        routes.append(Route("/mcp", endpoint=StreamableHTTPASGIApp(session_mgr), methods=["POST"]))
        routes.append(Route("/", endpoint=StreamableHTTPASGIApp(session_mgr), methods=["POST"]))

    routes.append(Mount("/", mcp_app))

    @asynccontextmanager
    async def lifespan(app: Starlette):
        async with AsyncExitStack() as stack:
            if session_mgr:
                await stack.enter_async_context(session_mgr.run())
            yield

    app = Starlette(routes=routes, lifespan=lifespan)
    if token_manager:
        require_auth = os.getenv("TAU_REQUIRE_AUTH", os.getenv("MOODLE_REQUIRE_AUTH", "1")) in ("1", "true", "True")
        app.add_middleware(
            BearerAuthMiddleware,
            token_manager=token_manager,
            require_auth=require_auth
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["mcp-session-id", "www-authenticate", "authorization"],
    )

    print(f"🚀 Starting Unified TAU MCP Server on http://{host}:{port}")
    print(f"   Streamable HTTP Endpoint: http://{host}:{port}/mcp (or root /)")
    print(f"   Health Check: http://{host}:{port}/health")

    config_uv = uvicorn.Config(app, host=host, port=port, log_level="info")
    uv_server = uvicorn.Server(config_uv)
    anyio.run(uv_server.serve)


def main():
    parser = argparse.ArgumentParser(description="Tel Aviv University (TAU) MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport protocol (default: stdio)"
    )
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE/HTTP (default: 8000)")
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE/HTTP (default: 0.0.0.0)")
    parser.add_argument("--profile", default=None, help="User profile name for isolated session storage")
    parser.add_argument("--no-moodle", action="store_true", help="Disable dynamic Moodle integration")
    parser.add_argument("--status", action="store_true", help="Print server authentication & plugin status and exit")

    args = parser.parse_args()

    include_moodle = not args.no_moodle
    server, portal, catalog, room_finder = create_server(profile=args.profile, include_moodle=include_moodle)

    if args.status:
        try:
            profile_data = portal.get_user_profile()
            print(json.dumps({
                "status": "authenticated",
                "profile": args.profile or config.TAU_PROFILE,
                "user": profile_data
            }, indent=2, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({
                "status": "unauthenticated or error",
                "error": str(e)
            }, indent=2))
        sys.exit(0)

    # Configure logging
    if args.transport == "stdio":
        # Direct all logging to stderr so stdout is purely for MCP JSON-RPC protocol
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)
        server.run(transport="stdio")
    elif args.transport == "streamable-http":
        logging.basicConfig(level=logging.INFO)
        run_streamable_http_server(server, host=args.host, port=args.port)
    else:
        logging.basicConfig(level=logging.INFO)
        server.run(transport="sse", host=args.host, port=args.port)

if __name__ == "__main__":
    main()
