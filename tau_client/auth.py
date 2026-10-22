import os
import time
import json
import urllib.parse
from typing import Dict, Tuple, Optional
import dotenv
from playwright.sync_api import sync_playwright

class TAUAuthManager:
    """
    Manages authentication for https://my.tau.ac.il/TAU_Student/
    Uses Playwright in headless mode to handle SSO, SAML redirects, and reCAPTCHA,
    and caches session cookies to disk so requests can be made directly.
    """

    PORTAL_URL = "https://my.tau.ac.il/TAU_Student/"
    DEFAULT_SESSION_FILE = ".tau_session.json"

    def __init__(
        self,
        username: Optional[str] = None,
        id_number: Optional[str] = None,
        password: Optional[str] = None,
        session_file: Optional[str] = None,
        env_file: Optional[str] = ".env"
    ):
        self.session_file = session_file or self.DEFAULT_SESSION_FILE
        self._load_credentials(username, id_number, password, env_file)

    def _load_credentials(self, username, id_number, password, env_file):
        # Load from .env if any are missing
        env_vals = dotenv.dotenv_values(env_file) if env_file and os.path.exists(env_file) else {}

        self.username = username or env_vals.get("USERNAME") or os.environ.get("TAU_USERNAME")
        self.id_number = id_number or env_vals.get("ID") or os.environ.get("TAU_ID")
        self.password = password or env_vals.get("PASSWORD") or os.environ.get("TAU_PASSWORD")

    def get_authenticated_session(self, force_refresh: bool = False) -> Tuple[Dict[str, str], str]:
        """
        Returns (cookies_dict, csrf_token).
        Loads from session file if available and fresh, otherwise logs in.
        """
        if not force_refresh and os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Check timestamp (keep cache for up to 30 minutes)
                cached_time = data.get("timestamp", 0)
                if time.time() - cached_time < 1800:
                    cookies = data.get("cookies", {})
                    csrf = data.get("csrf_token", "")
                    if cookies and csrf:
                        return cookies, csrf
            except Exception:
                pass

        return self.login()

    def login(self) -> Tuple[Dict[str, str], str]:
        """
        Performs headless Playwright authentication and returns (cookies, csrf_token).
        """
        if not self.username or not self.id_number or not self.password:
            raise ValueError("TAU credentials (USERNAME, ID, PASSWORD) must be provided in .env or constructor.")

        print(f"[TAUAuthManager] Authenticating student {self.username}...")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # 1. Navigate to portal
            page.goto(self.PORTAL_URL, wait_until="networkidle", timeout=60000)

            # 2. Check for IntroScreen "Got it" prompt
            try:
                got_it = page.locator("text='Got it, don’t show again'").or_(page.locator("text='Got it'"))
                if got_it.count() > 0:
                    got_it.first.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)
            except Exception:
                pass

            # 3. Fill in credentials on the SAML login form
            page.wait_for_selector("input[name='user_name']", timeout=15000)
            page.fill("input[name='user_name']", self.username)
            page.fill("input[name='id_number']", self.id_number)
            page.fill("input[name='password']", self.password)

            # 4. Submit login
            login_btn = page.locator("button:has-text('כניסה')").first
            login_btn.click()

            # 5. Wait for portal home page
            page.wait_for_load_state("networkidle")
            time.sleep(4)

            # 6. Extract cookies
            cookies_list = context.cookies()
            cookies_dict = {
                c["name"]: c["value"]
                for c in cookies_list
                if "tau.ac.il" in c["domain"]
            }

            # 7. Extract CSRF token from nr2Users cookie
            csrf_token = self._extract_csrf(cookies_dict)

            # Save to session cache
            session_data = {
                "timestamp": time.time(),
                "cookies": cookies_dict,
                "csrf_token": csrf_token,
                "username": self.username
            }
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2)

            browser.close()
            print("[TAUAuthManager] Authentication successful. Session cached.")
            return cookies_dict, csrf_token

    def invalidate_session(self):
        """Invalidates cached session file."""
        if os.path.exists(self.session_file):
            try:
                os.remove(self.session_file)
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
