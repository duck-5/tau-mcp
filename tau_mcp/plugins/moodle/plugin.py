"""
Moodle Plugin Bridge for tau_mcp.
Dynamically mounts moodle-mcp tools, resources, and prompts onto tau_mcp.
"""

import sys
import logging
from pathlib import Path

logger = logging.getLogger("tau_mcp.plugins.moodle")

def register_plugin(server, config, cache):
    """Dynamically initializes moodle_mcp and registers all its tools onto the central server."""
    # Find moodle_mcp package directory
    candidate_roots = [
        Path(__file__).resolve().parent.parent.parent.parent / "moodle_mcp",
        Path("../moodle_mcp").resolve(),
        Path("moodle_mcp").resolve(),
    ]

    for root in candidate_roots:
        if root.exists() and str(root.parent) not in sys.path:
            sys.path.insert(0, str(root.parent))

    try:
        from moodle_mcp.auth import MoodleAuth
        from moodle_mcp.client import MoodleClient
        from moodle_mcp.panopto import PanoptoManager
        from moodle_mcp.tools import register_all_tools

        profile = config.TAU_PROFILE
        auth = MoodleAuth(profile=profile)
        client = MoodleClient(auth=auth, profile=profile)
        panopto = PanoptoManager(moodle_client=client)

        register_all_tools(server, client, panopto)
        logger.info("[Plugin: Moodle] Successfully registered Moodle tools!")
        return True
    except Exception as e:
        logger.warning(f"[Plugin: Moodle] Could not load moodle_mcp: {e}")
        return False
