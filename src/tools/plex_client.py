"""Plex Media Server API client for MCP server."""

import os
from typing import Optional
import aiohttp

from ..models.plex import PlexLibrarySection, PlexMediaItem


class PlexError(Exception):
    """Base exception for Plex API errors."""
    pass


class PlexClient:
    """Async client for Plex Media Server API."""

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self.base_url = (base_url or os.getenv("PLEX_URL", "")).rstrip("/")
        self.token = token or os.getenv("PLEX_TOKEN", "")
        self._session: Optional[aiohttp.ClientSession] = None
        self._sections_cache: Optional[list[PlexLibrarySection]] = None

        if not self.base_url:
            raise PlexError("PLEX_URL not configured")
        if not self.token:
            raise PlexError("PLEX_TOKEN not configured")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "X-Plex-Token": self.token,
                    "Accept": "application/json",
                }
            )
        return self._session

    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, endpoint: str, **params) -> dict:
        """Make a GET request to the Plex API."""
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"

        try:
            async with session.get(url, params=params) as response:
                if response.status == 401:
                    raise PlexError("Invalid Plex token")
                if response.status >= 400:
                    text = await response.text()
                    raise PlexError(f"Plex API error {response.status}: {text}")
                return await response.json()
        except aiohttp.ClientError as e:
            raise PlexError(f"Connection error: {str(e)}")

    async def get_status(self) -> dict:
        """Get Plex server identity/status."""
        data = await self._request("/identity")
        mc = data.get("MediaContainer", {})
        return {
            "version": mc.get("version"),
            "machine_id": mc.get("machineIdentifier"),
        }

    async def get_library_sections(self) -> list[PlexLibrarySection]:
        """Get library sections, using cache if available."""
        if self._sections_cache is not None:
            return self._sections_cache

        data = await self._request("/library/sections")
        directories = data.get("MediaContainer", {}).get("Directory", [])

        sections = []
        for d in directories:
            section_type = d.get("type", "")
            if section_type in ("movie", "show"):
                sections.append(PlexLibrarySection(
                    key=d["key"],
                    title=d["title"],
                    type=section_type,
                ))

        self._sections_cache = sections
        return sections

    async def search_library(
        self,
        query: str,
        media_type: Optional[str] = None,
    ) -> list[PlexMediaItem]:
        """Search Plex library by title substring.

        Args:
            query: Title substring to search for
            media_type: Optional filter - "movie" or "tv"

        Returns:
            List of matching media items, capped at 50
        """
        sections = await self.get_library_sections()

        # Filter sections by media type if specified
        if media_type:
            # Map "tv" to Plex's "show" type
            plex_type = "show" if media_type == "tv" else media_type
            sections = [s for s in sections if s.type == plex_type]

        results = []
        for section in sections:
            data = await self._request(
                f"/library/sections/{section.key}/all",
                title=query,
            )
            metadata_list = data.get("MediaContainer", {}).get("Metadata", [])

            # Normalize Plex's "show" to "tv" for consistency
            normalized_type = "tv" if section.type == "show" else section.type

            for item in metadata_list:
                results.append(PlexMediaItem(
                    title=item.get("title", "Unknown"),
                    year=item.get("year"),
                    rating=item.get("rating"),
                    summary=item.get("summary"),
                    content_rating=item.get("contentRating"),
                    media_type=normalized_type,
                ))

                if len(results) >= 50:
                    return results

        return results
