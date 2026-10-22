"""
Dynamic Plugin Manager for tau_mcp.
Discovers and loads sub-system plugins (e.g. Moodle, Panopto, Library) without code replication.
"""

import sys
import logging
from pathlib import Path
from typing import Any, List, Dict

logger = logging.getLogger("tau_mcp.plugins")

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

        # 2. Check for moodle_mcp in parent directories if not already loaded
        if self.config.TAU_INCLUDE_MOODLE and "moodle" not in self.loaded_plugins:
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
                        mod.register_plugin(self.server, self.config, self.cache)
                        self.loaded_plugins.append(plugin_name)
                        logger.info(f"Loaded plugin: {plugin_name}")
                        return True
            except Exception as e:
                logger.warning(f"Error loading plugin '{plugin_name}': {e}")

        # Check if directory itself is a moodle-like package
        if (plugin_dir / "client.py").exists() and (plugin_dir / "auth.py").exists():
            return self._mount_moodle_package(plugin_dir.parent)

        return False

    def _try_load_moodle_bridge(self) -> bool:
        """Looks for moodle_mcp in standard adjacent locations and mounts it dynamically."""
        candidates = [
            Path(__file__).resolve().parent.parent.parent / "moodle_mcp",
            Path("../moodle_mcp").resolve(),
            Path("moodle_mcp").resolve(),
            Path("d:/ProgramFiles/Projects/random_stuff/moodle_mcp")
        ]

        for cand in candidates:
            if cand.exists() and (cand / "server.py").exists():
                return self._mount_moodle_package(cand.parent)

        # Check if already installed in Python environment
        try:
            import moodle_mcp
            return self._mount_moodle_package(None)
        except ImportError:
            pass

        return False

    def _mount_moodle_package(self, pkg_parent: Any) -> bool:
        """Dynamically mounts moodle_mcp tools, resources, and prompts onto MCPServer."""
        if pkg_parent and str(pkg_parent) not in sys.path:
            sys.path.insert(0, str(pkg_parent))

        try:
            from moodle_mcp.auth import MoodleAuth
            from moodle_mcp.client import MoodleClient
            from moodle_mcp.panopto import PanoptoManager
            from moodle_mcp.tools import register_all_tools

            profile = self.config.TAU_PROFILE
            auth = MoodleAuth(profile=profile)
            client = MoodleClient(auth=auth, profile=profile)
            panopto = PanoptoManager(moodle_client=client)

            # Register all tools from moodle_mcp into our central server
            register_all_tools(self.server, client, panopto)

            # Register Moodle Resources onto our server
            self._register_moodle_resources(client)

            self.loaded_plugins.append("moodle")
            logger.info("Successfully mounted moodle-mcp dynamically into tau-mcp!")
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
