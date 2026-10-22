"""
Dynamic Plugin Manager for tau_mcp.
Discovers and loads sub-system plugins (e.g. Moodle, Panopto, Library) without code replication.
"""

import sys
import logging
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger("tau_mcp.plugins")


def ensure_moodle_mcp_imported() -> bool:
    """Discovers moodle_mcp across candidate locations and dynamically registers it into sys.modules['moodle_mcp']."""
    if "moodle_mcp" in sys.modules:
        return True

    candidates = [
        Path(__file__).resolve().parent / "plugins" / "moodle" / "moodle-mcp",
        Path(__file__).resolve().parent / "plugins" / "moodle" / "moodle_mcp",
        Path(__file__).resolve().parent / "plugins" / "moodle",
        Path("../moodle-mcp").resolve(),
        Path("../moodle_mcp").resolve(),
        Path(__file__).resolve().parent.parent.parent / "moodle-mcp",
        Path(__file__).resolve().parent.parent.parent / "moodle_mcp",
        Path("/home/mantin-server/moodle-mcp"),
        Path("/moodle-mcp"),
        Path("/app/moodle-mcp"),
        Path("/app/plugins/moodle/moodle-mcp"),
    ]

    for cand in candidates:
        if cand.exists() and (cand / "server.py").exists():
            try:
                import importlib.util
                init_file = cand / "__init__.py"
                if not init_file.exists():
                    continue
                spec = importlib.util.spec_from_file_location(
                    "moodle_mcp",
                    init_file,
                    submodule_search_locations=[str(cand)]
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules["moodle_mcp"] = mod
                    spec.loader.exec_module(mod)
                    if str(cand) not in sys.path:
                        sys.path.insert(0, str(cand))
                    if str(cand.parent) not in sys.path:
                        sys.path.insert(0, str(cand.parent))
                    logger.info(f"Dynamically mapped 'moodle_mcp' package from {cand}")
                    return True
            except Exception as e:
                logger.warning(f"Error loading moodle_mcp candidate from {cand}: {e}")

    # Check if already installed in Python environment
    try:
        import moodle_mcp  # noqa: F401
        return True
    except ImportError:
        pass

    return False


class PluginManager:
    """Manages dynamic discovery, loading, and tool registration for tau_mcp plugins."""

    def __init__(self, server: Any, config: Any, cache: Any):
        self.server = server
        self.config = config
        self.cache = cache
        self.loaded_plugins: List[str] = []

    def load_all_plugins(self) -> List[str]:
        """Discovers and registers all available plugins."""
        plugins_dir = Path(__file__).resolve().parent / "plugins"

        # 1. Scan tau_mcp/plugins/* directories
        if plugins_dir.exists():
            for item in plugins_dir.iterdir():
                if item.is_dir() and not item.name.startswith(("_", ".")):
                    self._load_plugin_from_dir(item)

        # 2. Check for moodle_mcp fallback if not already loaded
        if getattr(self.config, "TAU_INCLUDE_MOODLE", True) and "moodle" not in self.loaded_plugins:
            self._try_load_moodle_bridge()

        return self.loaded_plugins

    def _load_plugin_from_dir(self, plugin_dir: Path) -> bool:
        """Attempts to load a plugin from a directory."""
        plugin_name = plugin_dir.name
        logger.debug(f"Attempting to load plugin: {plugin_name} from {plugin_dir}")

        if str(plugin_dir) not in sys.path:
            sys.path.insert(0, str(plugin_dir))

        plugin_py = plugin_dir / "plugin.py"
        if plugin_py.exists():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(f"tau_mcp.plugins.{plugin_name}", plugin_py)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, "register_plugin"):
                        success = mod.register_plugin(self.server, self.config, self.cache)
                        if success:
                            if plugin_name not in self.loaded_plugins:
                                self.loaded_plugins.append(plugin_name)
                            logger.info(f"Loaded plugin: {plugin_name}")
                            return True
            except Exception as e:
                logger.warning(f"Error loading plugin '{plugin_name}': {e}")

        # Check if directory itself is a moodle-like package
        if (plugin_dir / "client.py").exists() and (plugin_dir / "auth.py").exists():
            return self._mount_moodle_package()

        return False

    def _try_load_moodle_bridge(self) -> bool:
        """Attempts to discover moodle_mcp and mount it dynamically."""
        if ensure_moodle_mcp_imported():
            return self._mount_moodle_package()
        return False

    def _mount_moodle_package(self) -> bool:
        """Dynamically mounts moodle_mcp tools, resources, and prompts onto MCPServer."""
        if not ensure_moodle_mcp_imported():
            logger.warning("Could not locate or import moodle_mcp package.")
            return False

        try:
            from moodle_mcp.auth import MoodleAuth
            from moodle_mcp.client import MoodleClient
            from moodle_mcp.panopto import PanoptoManager
            from moodle_mcp.tools import register_all_tools

            profile = getattr(self.config, "TAU_PROFILE", None) or "default"
            # Map default or full username to primary Moodle profile (e.g. 'yuval') if matching
            if profile in ("default", "") or profile == getattr(self.config, "TAU_USERNAME", ""):
                try:
                    from moodle_mcp.config import get_primary_profile
                    m_prim = get_primary_profile()
                    if m_prim and m_prim != "default":
                        profile = m_prim
                except Exception:
                    pass

            auth = MoodleAuth(profile=profile)
            client = MoodleClient(auth=auth, profile=profile)
            panopto = PanoptoManager(moodle_client=client)

            # Register all tools from moodle_mcp into our central server
            register_all_tools(self.server, client, panopto)

            # Register Moodle Resources onto our server
            self._register_moodle_resources(client)

            if "moodle" not in self.loaded_plugins:
                self.loaded_plugins.append("moodle")
            logger.info(f"Successfully mounted moodle-mcp dynamically into tau-mcp (profile: {profile})!")
            return True
        except Exception as e:
            logger.warning(f"Could not dynamically mount moodle-mcp: {e}")
            return False

    def _register_moodle_resources(self, client: Any) -> None:
        """Registers moodle:// resources onto the central server."""
        import json

        @self.server.resource("moodle://courses")
        def get_courses_resource() -> str:
            courses = client.get_enrolled_courses()
            return json.dumps(courses, indent=2, ensure_ascii=False)

        @self.server.resource("moodle://upcoming")
        def get_upcoming_resource() -> str:
            upcoming = client.get_upcoming_assignments(days_ahead=7)
            return json.dumps(upcoming, indent=2, ensure_ascii=False)

        @self.server.resource("moodle://grades")
        def get_grades_resource() -> str:
            summary = client.get_grades_summary()
            return json.dumps(summary, indent=2, ensure_ascii=False)

        @self.server.resource("moodle://dashboard")
        def get_dashboard_resource() -> str:
            dash = client.get_dashboard()
            return json.dumps(dash, indent=2, ensure_ascii=False)
