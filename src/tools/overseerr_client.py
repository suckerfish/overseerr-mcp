"""Overseerr API client for MCP server."""

import os
from datetime import datetime, timedelta
from typing import Optional
import aiohttp
from pydantic import ValidationError
from urllib.parse import quote

from ..models.overseerr import (
    MediaType,
    RequestStatus,
    MediaStatus,
    MediaSearchResult,
    MediaRequest,
    UserInfo,
    RequestResponse,
    get_media_status_text,
)


class OverseerrError(Exception):
    """Base exception for Overseerr API errors."""
    pass


class OverseerrClient:
    """Async client for Overseerr API."""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or os.getenv("OVERSEERR_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("OVERSEERR_API_KEY", "")
        self._session: Optional[aiohttp.ClientSession] = None

        if not self.base_url:
            raise OverseerrError("OVERSEERR_URL not configured")
        if not self.api_key:
            raise OverseerrError("OVERSEERR_API_KEY not configured")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "X-Api-Key": self.api_key,
                    "Content-Type": "application/json",
                }
            )
        return self._session

    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an API request."""
        session = await self._get_session()
        url = f"{self.base_url}/api/v1{endpoint}"

        try:
            async with session.request(method, url, **kwargs) as response:
                if response.status == 401:
                    raise OverseerrError("Invalid API key")
                if response.status == 404:
                    raise OverseerrError(f"Resource not found: {endpoint}")
                if response.status >= 400:
                    text = await response.text()
                    raise OverseerrError(f"API error {response.status}: {text}")

                return await response.json()
        except aiohttp.ClientError as e:
            raise OverseerrError(f"Connection error: {str(e)}")

    async def get_status(self) -> dict:
        """Get server status."""
        return await self._request("GET", "/status")

    async def search_media(
        self,
        query: str,
        page: int = 1,
        media_type: Optional[MediaType] = None,
    ) -> list[dict]:
        """Search for movies and TV shows with availability status."""
        # URL encode query - Overseerr requires this for spaces/special chars
        params = {"query": quote(query, safe=""), "page": page}

        # Use combined search endpoint
        data = await self._request("GET", "/search", params=params)

        results = []
        for item in data.get("results", []):
            # Filter by media type if specified
            item_type = item.get("mediaType")
            if media_type and item_type != media_type.value:
                continue
            if item_type not in ("movie", "tv"):
                continue

            try:
                parsed = MediaSearchResult(**item)

                # Extract status from mediaInfo if present
                media_info = item.get("mediaInfo")
                status = MediaStatus.UNKNOWN
                if media_info:
                    status_val = media_info.get("status", 1)
                    try:
                        status = MediaStatus(status_val)
                    except ValueError:
                        status = MediaStatus.UNKNOWN

                results.append({
                    "id": parsed.id,
                    "mediaType": parsed.mediaType,
                    "title": parsed.display_title,
                    "year": parsed.year,
                    "overview": parsed.overview,
                    "voteAverage": parsed.voteAverage,
                    "status": status.value,
                    "status_text": get_media_status_text(status),
                })
            except ValidationError:
                continue

        return results

    async def get_users(self) -> list[UserInfo]:
        """Get all users."""
        data = await self._request("GET", "/user", params={"take": 100})

        results = []
        for item in data.get("results", []):
            try:
                results.append(UserInfo(**item))
            except ValidationError:
                continue

        return results

    async def get_user(self, user_id: int) -> UserInfo:
        """Get a specific user by ID."""
        data = await self._request("GET", f"/user/{user_id}")
        return UserInfo(**data)

    async def get_requests(
        self,
        status: Optional[RequestStatus] = None,
        take: int = 50,
        skip: int = 0,
        sort_by: str = "added",
    ) -> list[MediaRequest]:
        """Get media requests with optional filtering."""
        params = {
            "take": take,
            "skip": skip,
            "sort": sort_by,
        }
        if status:
            params["filter"] = status.value

        data = await self._request("GET", "/request", params=params)

        results = []
        for item in data.get("results", []):
            try:
                request = MediaRequest(**item)
                results.append(request)
            except ValidationError:
                continue

        return results

    async def get_requests_with_media_info(
        self,
        status: Optional[RequestStatus] = None,
        since: Optional[datetime] = None,
        take: int = 50,
    ) -> list[dict]:
        """Get requests with full media titles resolved."""
        requests = await self.get_requests(status=status, take=take)

        enriched = []
        for req in requests:
            # Filter by date if specified (handle timezone-aware comparison)
            if since:
                req_time = req.createdAt.replace(tzinfo=None) if req.createdAt.tzinfo else req.createdAt
                since_time = since.replace(tzinfo=None) if since.tzinfo else since
                if req_time < since_time:
                    continue

            # Try to get media title
            title = "Unknown"
            if req.media and req.media.tmdbId:
                try:
                    if req.type == MediaType.MOVIE:
                        media_data = await self._request("GET", f"/movie/{req.media.tmdbId}")
                        title = media_data.get("title", "Unknown Movie")
                    else:
                        media_data = await self._request("GET", f"/tv/{req.media.tmdbId}")
                        title = media_data.get("name", "Unknown TV Show")
                except OverseerrError:
                    pass

            enriched.append({
                "id": req.id,
                "title": title,
                "type": req.type.value,
                "status": req.status_text,
                "requested_by": req.requester_name,
                "requested_at": req.createdAt.isoformat(),
                "user_id": req.requestedBy.id if req.requestedBy else None,
            })

        return enriched

    async def get_user_requests(self, user_id: int) -> list[dict]:
        """Get all requests for a specific user."""
        # Get user info first
        user = await self.get_user(user_id)

        # Get all requests and filter by user
        all_requests = await self.get_requests(take=100)
        user_requests = [r for r in all_requests if r.requestedBy and r.requestedBy.id == user_id]

        enriched = []
        for req in user_requests:
            title = "Unknown"
            if req.media and req.media.tmdbId:
                try:
                    if req.type == MediaType.MOVIE:
                        media_data = await self._request("GET", f"/movie/{req.media.tmdbId}")
                        title = media_data.get("title", "Unknown Movie")
                    else:
                        media_data = await self._request("GET", f"/tv/{req.media.tmdbId}")
                        title = media_data.get("name", "Unknown TV Show")
                except OverseerrError:
                    pass

            enriched.append({
                "id": req.id,
                "title": title,
                "type": req.type.value,
                "status": req.status_text,
                "requested_at": req.createdAt.isoformat(),
            })

        return {
            "user": user.name,
            "user_id": user_id,
            "request_count": len(enriched),
            "requests": enriched,
        }

    async def request_media(
        self,
        media_type: MediaType,
        tmdb_id: int,
        seasons: Optional[list[int]] = None,
    ) -> RequestResponse:
        """Request a movie or TV show."""
        payload = {"mediaType": media_type.value, "mediaId": tmdb_id}

        if media_type == MediaType.TV and seasons:
            payload["seasons"] = seasons
        elif media_type == MediaType.TV:
            # Request all seasons by default for TV
            payload["seasons"] = "all"

        data = await self._request("POST", "/request", json=payload)
        return RequestResponse(**data)

    async def get_movie_details(self, tmdb_id: int) -> dict:
        """Get movie details by TMDB ID."""
        return await self._request("GET", f"/movie/{tmdb_id}")

    async def get_tv_details(self, tmdb_id: int) -> dict:
        """Get TV show details by TMDB ID."""
        return await self._request("GET", f"/tv/{tmdb_id}")

    async def get_media_status(
        self,
        tmdb_id: int,
        media_type: MediaType,
    ) -> dict:
        """Get availability status for a movie or TV show.

        Args:
            tmdb_id: TMDB ID of the media
            media_type: Either MediaType.MOVIE or MediaType.TV

        Returns:
            Dict with status information
        """
        if media_type == MediaType.MOVIE:
            data = await self._request("GET", f"/movie/{tmdb_id}")
            title = data.get("title", "Unknown Movie")
        else:
            data = await self._request("GET", f"/tv/{tmdb_id}")
            title = data.get("name", "Unknown TV Show")

        media_info = data.get("mediaInfo")

        # Default to UNKNOWN if no mediaInfo
        status = MediaStatus.UNKNOWN
        has_request = False
        request_status = None

        if media_info:
            status_val = media_info.get("status", 1)
            try:
                status = MediaStatus(status_val)
            except ValueError:
                status = MediaStatus.UNKNOWN

            requests = media_info.get("requests", [])
            has_request = len(requests) > 0
            if has_request and requests:
                latest_request = requests[-1]
                req_status = latest_request.get("status")
                request_status_map = {1: "Pending", 2: "Approved", 3: "Declined"}
                request_status = request_status_map.get(req_status, "Unknown")

        result = {
            "tmdb_id": tmdb_id,
            "title": title,
            "media_type": media_type.value,
            "status": status.value,
            "status_text": get_media_status_text(status),
            "has_request": has_request,
            "request_status": request_status,
        }

        # Add TV-specific info
        if media_type == MediaType.TV:
            seasons = data.get("seasons", [])
            regular_seasons = [s for s in seasons if s.get("seasonNumber", 0) > 0]
            result["seasons_count"] = len(regular_seasons)

        return result
