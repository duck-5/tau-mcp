"""
Authentication and session management for the Tel Aviv University student portal.
Supports:
1. Automated Playwright NetIQ SAML SSO login with invisible reCAPTCHA handling
2. Persistent local session caching in ~/.tau_mcp/profiles/{profile}/portal_session.json
3. Multi-profile isolation and stateless execution modes
"""

import os
import json
import time
import logging
import urllib.parse
from pathlib import Path
from typing import Dict, Tuple, Optional, Any
from playwright.sync_api import sync_playwright

from tau_mcp.config import (
    PORTAL_URL,
    TAU_USERNAME,
    TAU_ID,
    TAU_PASSWORD,
    sanitize_profile_name,
    get_profile_paths,
)

logger = logging.getLogger("tau_mcp.auth")

class TAUAuthError(Exception):
    """Raised when authentication with TAU portal fails."""
    pass

class TAUAuthManager:
    """
    Manages authenticated sessions with https://my.tau.ac.il/TAU_Student/.
    Uses headless Playwright to negotiate NetIQ SAML SSO and extract session cookies + CSRF tokens.
    """

    def __init__(
        self,
        username: Optional[str] = None,
        id_number: Optional[str] = None,
        password: Optional[str] = None,
        profile: Optional[str] = None,
        session_file: Optional[Path] = None,
    ):
        self.profile = sanitize_profile_name(profile)
        self.username = username or TAU_USERNAME
        self.id_number = id_number or TAU_ID
        self.password = password or TAU_PASSWORD

        if session_file:
            self.session_file = Path(session_file)
        else:
            self.session_file = get_profile_paths(self.profile)["portal_session_file"]

        self.cookies: Dict[str, str] = {}
        self.csrf_token: str = ""

    def get_authenticated_session(self, force_refresh: bool = False) -> Tuple[Dict[str, str], str]:
        """
        Returns (cookies_dict, csrf_token).
        Loads cached session if fresh (<30 min old), otherwise performs automated login.
        """
        if not force_refresh and self.load_cached_session():
            return self.cookies, self.csrf_token

        return self.login()

    def load_cached_session(self) -> bool:
        """Loads session cookies and CSRF token from disk if valid."""
        if self.profile == "stateless" or os.getenv("TAU_STATELESS") == "1":
            return False

        if not self.session_file.exists():
            return False

        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Session valid for up to 30 minutes
            cached_time = data.get("timestamp", 0)
            if time.time() - cached_time > 1800:
                logger.debug("Portal session cache expired.")
                return False

            cookies = data.get("cookies", {})
            csrf = data.get("csrf_token", "")

            if cookies and csrf and "ASP.NET_SessionId" in cookies:
                self.cookies = cookies
                self.csrf_token = csrf
                logger.debug(f"Loaded valid portal session cache for profile '{self.profile}'")
                return True
        except Exception as e:
            logger.warning(f"Error loading portal session cache: {e}")

        return False

    def save_session(self) -> None:
        """Saves current session cookies and CSRF token to disk (never saving raw password)."""
        if self.profile == "stateless" or os.getenv("TAU_STATELESS") == "1":
            return

        try:
            self.session_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "profile": self.profile,
                "timestamp": time.time(),
                "cookies": self.cookies,
                "csrf_token": self.csrf_token,
                "username": self.username
            }
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            logger.info(f"Saved portal session cache to {self.session_file}")
        except Exception as e:
            logger.warning(f"Could not save portal session cache: {e}")

    def login(self) -> Tuple[Dict[str, str], str]:
        """Performs Playwright authentication and returns (cookies, csrf_token)."""
        import concurrent.futures
        try:
            import asyncio
            asyncio.get_running_loop()
            # Inside an active asyncio event loop: execute in a separate thread
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(self._do_playwright_login).result()
        except RuntimeError:
            # No running event loop
            return self._do_playwright_login()

    def _do_playwright_login(self) -> Tuple[Dict[str, str], str]:
        """Internal worker performing Playwright navigation and extraction."""
        if not self.username or not self.id_number or not self.password:
            raise TAUAuthError(
                "TAU credentials missing. Please set USERNAME, ID, and PASSWORD in your .env or environment."
            )

        logger.info(f"Authenticating student portal session for profile '{self.profile}'...")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()

                # 1. Navigate to portal
                page.goto(PORTAL_URL, wait_until="networkidle", timeout=60000)

                # 2. Dismiss IntroScreen overlay if present
                try:
                    got_it = page.locator("text='Got it, don’t show again'").or_(page.locator("text='Got it'"))
                    if got_it.count() > 0:
                        got_it.first.click()
                        page.wait_for_load_state("networkidle")
                        time.sleep(1)
                except Exception:
                    pass

                # 3. Fill in SAML SSO credentials
                page.wait_for_selector("input[name='user_name']", timeout=15000)
                page.fill("input[name='user_name']", self.username)
                page.fill("input[name='id_number']", self.id_number)
                page.fill("input[name='password']", self.password)

                # 4. Submit form
                login_btn = page.locator("button:has-text('כניסה')").first
                login_btn.click()

                # 5. Wait for redirect back to my.tau.ac.il/TAU_Student/
                page.wait_for_load_state("networkidle")
                time.sleep(4)

                # 6. Extract cookies
                cookies_list = context.cookies()
                self.cookies = {
                    c["name"]: c["value"]
                    for c in cookies_list
                    if "tau.ac.il" in c["domain"]
                }

                # 7. Extract CSRF token from nr2Users cookie
                self.csrf_token = self._extract_csrf(self.cookies)

                browser.close()

                if not self.csrf_token or "ASP.NET_SessionId" not in self.cookies:
                    raise TAUAuthError("Login failed: missing session cookies or CSRF token.")

                self.save_session()
                logger.info("TAU Portal authentication successful.")
                return self.cookies, self.csrf_token

        except Exception as e:
            raise TAUAuthError(f"Playwright authentication failed: {e}") from e

    def invalidate_session(self) -> None:
        """Invalidates in-memory and disk session."""
        self.cookies = {}
        self.csrf_token = ""
        if self.session_file.exists():
            try:
                self.session_file.unlink()
            except Exception:
                pass

    @staticmethod
    def _extract_csrf(cookies: Dict[str, str]) -> str:
        if "nr2Users" in cookies:
            unquoted = urllib.parse.unquote(cookies["nr2Users"])
            for part in unquoted.split(";"):
                if part.startswith("crf="):
                    return part.split("=", 1)[1]
        return ""
