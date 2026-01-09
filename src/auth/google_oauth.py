"""
Google OAuth Authentication

Handles OAuth 2.0 authentication for Gmail and Google Calendar APIs.
Manages tokens, refresh, and credential storage.
"""

import os
import json
from pathlib import Path
from typing import Optional, List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
import structlog

logger = structlog.get_logger()


# OAuth scopes required for Gmail and Calendar
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
]

ALL_SCOPES = GMAIL_SCOPES + CALENDAR_SCOPES


class GoogleOAuth:
    """
    Manages Google OAuth 2.0 authentication and API access.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_file: str = "./data/tokens/google_token.json",
        scopes: Optional[List[str]] = None,
    ):
        """
        Initialize Google OAuth manager.

        Args:
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret
            token_file: Path to store OAuth tokens
            scopes: List of OAuth scopes (default: all Gmail + Calendar scopes)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_file = Path(token_file)
        self.scopes = scopes or ALL_SCOPES

        # Ensure token directory exists
        self.token_file.parent.mkdir(parents=True, exist_ok=True)

        self._credentials: Optional[Credentials] = None

        logger.info("google_oauth_initialized", scopes=self.scopes)

    @property
    def credentials(self) -> Credentials:
        """
        Get valid OAuth credentials, refreshing if needed.

        Returns:
            Valid OAuth credentials

        Raises:
            RuntimeError: If not authenticated
        """
        if self._credentials is None:
            self._credentials = self._load_credentials()

        if self._credentials is None:
            raise RuntimeError(
                "Not authenticated. Run authenticate() first or use authenticate.py script."
            )

        # Refresh if expired
        if self._credentials.expired and self._credentials.refresh_token:
            logger.info("refreshing_oauth_token")
            self._credentials.refresh(Request())
            self._save_credentials(self._credentials)
            logger.info("oauth_token_refreshed")

        return self._credentials

    def authenticate(self, force: bool = False) -> Credentials:
        """
        Perform OAuth authentication flow.

        Args:
            force: Force re-authentication even if credentials exist

        Returns:
            OAuth credentials
        """
        # Check if we already have valid credentials
        if not force:
            creds = self._load_credentials()
            if creds and creds.valid:
                logger.info("using_existing_credentials")
                self._credentials = creds
                return creds

        logger.info("starting_oauth_flow")

        # Create OAuth flow
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            },
            scopes=self.scopes,
        )

        # Run local server flow
        creds = flow.run_local_server(
            port=0,
            authorization_prompt_message="Please visit this URL to authorize: {url}",
            success_message="Authentication successful! You may close this window.",
        )

        # Save credentials
        self._save_credentials(creds)
        self._credentials = creds

        logger.info("authentication_complete")

        return creds

    def _load_credentials(self) -> Optional[Credentials]:
        """
        Load credentials from token file.

        Returns:
            Credentials if file exists, None otherwise
        """
        if not self.token_file.exists():
            logger.debug("token_file_not_found", path=str(self.token_file))
            return None

        try:
            with open(self.token_file, "r") as f:
                token_data = json.load(f)

            creds = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri"),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=token_data.get("scopes"),
            )

            logger.info("credentials_loaded", path=str(self.token_file))
            return creds

        except Exception as e:
            logger.error("failed_to_load_credentials", error=str(e))
            return None

    def _save_credentials(self, creds: Credentials) -> None:
        """
        Save credentials to token file.

        Args:
            creds: Credentials to save
        """
        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
        }

        with open(self.token_file, "w") as f:
            json.dump(token_data, f, indent=2)

        # Secure the file (only readable by owner)
        os.chmod(self.token_file, 0o600)

        logger.info("credentials_saved", path=str(self.token_file))

    def is_authenticated(self) -> bool:
        """
        Check if we have valid credentials.

        Returns:
            True if authenticated
        """
        try:
            creds = self._load_credentials()
            return creds is not None and (creds.valid or creds.refresh_token is not None)
        except Exception:
            return False

    def revoke(self) -> None:
        """
        Revoke OAuth credentials and delete token file.
        """
        if self._credentials:
            try:
                self._credentials.revoke(Request())
                logger.info("credentials_revoked")
            except Exception as e:
                logger.warning("failed_to_revoke_credentials", error=str(e))

        if self.token_file.exists():
            self.token_file.unlink()
            logger.info("token_file_deleted")

        self._credentials = None

    def get_gmail_service(self) -> Resource:
        """
        Get authenticated Gmail API service.

        Returns:
            Gmail API service object
        """
        return build("gmail", "v1", credentials=self.credentials)

    def get_calendar_service(self) -> Resource:
        """
        Get authenticated Calendar API service.

        Returns:
            Calendar API service object
        """
        return build("calendar", "v3", credentials=self.credentials)


# Global OAuth instance
_oauth_instance: Optional[GoogleOAuth] = None


def get_oauth() -> GoogleOAuth:
    """
    Get the global OAuth instance.

    Returns:
        GoogleOAuth instance

    Raises:
        RuntimeError: If OAuth not initialized
    """
    if _oauth_instance is None:
        raise RuntimeError("OAuth not initialized. Call init_oauth() first.")
    return _oauth_instance


def init_oauth(
    client_id: str,
    client_secret: str,
    token_file: str = "./data/tokens/google_token.json",
) -> GoogleOAuth:
    """
    Initialize the global OAuth instance.

    Args:
        client_id: Google OAuth client ID
        client_secret: Google OAuth client secret
        token_file: Path to token file

    Returns:
        GoogleOAuth instance
    """
    global _oauth_instance
    _oauth_instance = GoogleOAuth(client_id, client_secret, token_file)
    return _oauth_instance
