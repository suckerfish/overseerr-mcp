"""Overseerr MCP Server - Media request management via MCP protocol."""

import argparse
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from .models.overseerr import MediaType, RequestStatus
from .tools.overseerr_client import OverseerrClient, OverseerrError

load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("overseerr-mcp")

# Global client instance
_client: Optional[OverseerrClient] = None


def get_client() -> OverseerrClient:
    """Get or create the Overseerr client."""
    global _client
    if _client is None:
        try:
            _client = OverseerrClient()
        except OverseerrError as e:
            raise ToolError(f"Configuration error: {str(e)}")
    return _client


@mcp.tool()
async def search_media(
    query: str,
    media_type: Optional[str] = None,
) -> dict:
    """Search for movies and TV shows in Overseerr.

    Use this to find media by title before making a request.
    Returns TMDB IDs needed for requesting media.

    Args:
        query: Search term (movie or TV show title)
        media_type: Optional filter - "movie" or "tv"

    Returns:
        List of matching movies/TV shows with TMDB IDs, titles, years, ratings,
        and availability status
    """
    try:
        client = get_client()

        type_filter = None
        if media_type:
            type_filter = MediaType(media_type.lower())

        results = await client.search_media(query, media_type=type_filter)

        return {
            "query": query,
            "count": len(results),
            "results": [
                {
                    "tmdb_id": r["id"],
                    "title": r["title"],
                    "year": r["year"],
                    "type": r["mediaType"].value,
                    "overview": (r["overview"][:200] + "...") if r["overview"] and len(r["overview"]) > 200 else r["overview"],
                    "rating": round(r["voteAverage"], 1) if r["voteAverage"] else None,
                    "status": r["status"],
                    "status_text": r["status_text"],
                }
                for r in results[:20]  # Limit to top 20
            ],
        }
    except OverseerrError as e:
        raise ToolError(f"Search failed: {str(e)}")
    except Exception as e:
        raise ToolError(f"Unexpected error: {str(e)}")


@mcp.tool()
async def get_requests(
    status: Optional[str] = None,
    media_status: Optional[str] = None,
    days: Optional[int] = None,
    limit: int = 20,
    show_all: bool = False,
) -> dict:
    """Get media requests with user information.

    Lists all requests showing who requested what and when.
    Perfect for queries like "list all requests from the last week and who requested them".

    Args:
        status: Filter by request approval status - "pending" or "approved"
        media_status: Filter by availability - "available", "processing", "unavailable", or "failed"
        days: Optional - only show requests from the last N days
        limit: Maximum number of requests to return (default 20)
        show_all: Set to true to return all matching requests (ignores limit)

    Returns:
        List of requests with titles, requesters, request status, and media availability
    """
    try:
        client = get_client()

        # Determine API filter - media_status takes priority (more specific)
        # API supports: all, approved, available, pending, processing, unavailable, failed
        api_filter = None
        client_side_status_filter = None

        if media_status:
            media_status_lower = media_status.lower()
            if media_status_lower in ("available", "processing", "unavailable", "failed"):
                api_filter = media_status_lower
            # If both filters specified, we'll filter request status client-side
            if status:
                client_side_status_filter = status.lower()
        elif status:
            status_lower = status.lower()
            if status_lower in ("pending", "approved"):
                api_filter = status_lower

        since = None
        if days:
            since = datetime.now() - timedelta(days=days)

        take_count = 10000 if show_all else limit

        requests = await client.get_requests_with_media_info(
            filter_by=api_filter,
            since=since,
            take=take_count,
        )

        # Client-side filter by request status if needed (when both filters specified)
        if client_side_status_filter:
            status_text_map = {"pending": "Pending", "approved": "Approved"}
            target = status_text_map.get(client_side_status_filter)
            if target:
                requests = [r for r in requests if r.get("request_status") == target]

        return {
            "filter": {
                "status": status,
                "media_status": media_status,
                "days": days,
                "show_all": show_all,
            },
            "count": len(requests),
            "requests": requests,
        }
    except OverseerrError as e:
        raise ToolError(f"Failed to get requests: {str(e)}")
    except Exception as e:
        raise ToolError(f"Unexpected error: {str(e)}")


@mcp.tool()
async def get_users() -> dict:
    """Get all Overseerr users.

    Lists all users with their IDs and request counts.
    Use the user ID to get a specific user's requests.

    Returns:
        List of users with IDs, names, and request counts
    """
    try:
        client = get_client()
        users = await client.get_users()

        return {
            "count": len(users),
            "users": [
                {
                    "id": u.id,
                    "name": u.name,
                    "email": u.email,
                    "request_count": u.requestCount,
                }
                for u in users
            ],
        }
    except OverseerrError as e:
        raise ToolError(f"Failed to get users: {str(e)}")
    except Exception as e:
        raise ToolError(f"Unexpected error: {str(e)}")


@mcp.tool()
async def get_user_requests(
    user_id: int,
    media_status: Optional[str] = None,
    limit: int = 20,
    show_all: bool = False,
) -> dict:
    """Get all requests made by a specific user.

    Shows all media requests from a particular user.
    Get the user_id from the get_users tool.

    Args:
        user_id: The Overseerr user ID
        media_status: Filter by availability - "processing", "available", or "partially_available"
        limit: Maximum number of requests to return (default 20)
        show_all: Set to true to return all matching requests (ignores limit)

    Returns:
        User info and their request history filtered by media status
    """
    try:
        client = get_client()

        # Map input to display text used in results
        status_filter = None
        if media_status:
            status_map = {
                "processing": "Processing",
                "available": "Available",
                "partially_available": "Partially Available",
                "requested": "Requested",
                "not_requested": "Not Requested",
            }
            status_filter = status_map.get(media_status.lower())

        take_count = 10000 if show_all else limit

        result = await client.get_user_requests(
            user_id,
            media_status_filter=status_filter,
            limit=take_count,
        )
        return result
    except OverseerrError as e:
        raise ToolError(f"Failed to get user requests: {str(e)}")
    except Exception as e:
        raise ToolError(f"Unexpected error: {str(e)}")


@mcp.tool()
async def request_media(
    tmdb_id: int,
    media_type: str,
    seasons: Optional[str] = None,
    confirm: bool = False,
) -> dict:
    """Request a movie or TV show to be added to Plex.

    Use search_media first to find the TMDB ID for the content you want.

    By default, returns a preview showing title, metadata, and per-season availability
    for TV shows. Set confirm=true to actually submit the request.

    For TV shows with multiple seasons, you must specify which seasons to request.
    Single-season shows are auto-selected.

    Args:
        tmdb_id: TMDB ID of the movie or TV show (from search results)
        media_type: "movie" or "tv"
        seasons: For TV shows - comma-separated season numbers (e.g., "1,2,3") or "all"
        confirm: Set to true to actually submit the request. Without this, returns a preview.

    Returns:
        Preview with title, overview, genres, rating, and season availability (TV),
        or confirmation if confirm=true
    """
    try:
        client = get_client()
        mt = MediaType(media_type.lower())

        # Fetch media details for preview/confirmation
        if mt == MediaType.MOVIE:
            details = await client.get_movie_details(tmdb_id)
            title = details.get("title", "Unknown")
            year = str(details.get("releaseDate", ""))[:4] or None
        else:
            details = await client.get_tv_details(tmdb_id)
            title = details.get("name", "Unknown")
            year = str(details.get("firstAirDate", ""))[:4] or None

        # Extract common metadata
        tagline = details.get("tagline")
        overview = details.get("overview", "")
        if overview and len(overview) > 200:
            overview = overview[:200] + "..."
        genres = [g.get("name") for g in details.get("genres", [])]
        rating = round(details.get("voteAverage", 0), 1) or None

        # For TV shows, extract per-season status
        season_details = []
        if mt == MediaType.TV:
            media_info = details.get("mediaInfo", {})
            season_statuses = {s.get("seasonNumber"): s.get("status", 1) for s in media_info.get("seasons", [])}

            for s in details.get("seasons", []):
                season_num = s.get("seasonNumber", 0)
                if season_num == 0:  # Skip specials
                    continue
                status_code = season_statuses.get(season_num, 1)
                status_map = {1: "Not Requested", 2: "Requested", 3: "Processing", 4: "Partially Available", 5: "Available"}
                season_details.append({
                    "season": season_num,
                    "episodes": s.get("episodeCount", 0),
                    "status": status_map.get(status_code, "Unknown"),
                })

        # Preview mode - return details without requesting
        if not confirm:
            preview = {
                "preview": True,
                "tmdb_id": tmdb_id,
                "title": title,
                "year": year,
                "type": mt.value,
                "tagline": tagline,
                "overview": overview,
                "genres": genres,
                "rating": rating,
            }

            if mt == MediaType.TV:
                preview["seasons"] = season_details
                if seasons:
                    preview["selected_seasons"] = seasons
                    preview["message"] = "Call again with confirm=true to submit this request"
                elif len(season_details) == 1:
                    # Single season show - auto-select
                    preview["selected_seasons"] = str(season_details[0]["season"])
                    preview["message"] = "Call again with confirm=true to request season 1"
                else:
                    # Multi-season show - require selection
                    not_requested = [s["season"] for s in season_details if s["status"] == "Not Requested"]
                    if not_requested:
                        preview["message"] = f"Specify seasons to request (e.g., seasons=\"{','.join(map(str, not_requested[:3]))}\" or seasons=\"all\")"
                    else:
                        preview["message"] = "All seasons already requested/available. Specify seasons parameter to re-request specific seasons."
            else:
                preview["message"] = "Call again with confirm=true to submit this request"

            return preview

        # Confirmed - submit the request
        season_list = None
        seasons_requested = None

        if mt == MediaType.TV:
            if seasons and seasons.lower() == "all":
                # Explicitly requesting all seasons
                season_list = None  # Client defaults to "all"
                seasons_requested = "all"
            elif seasons:
                # Specific seasons requested
                season_list = [int(s.strip()) for s in seasons.split(",")]
                seasons_requested = seasons
            elif len(season_details) == 1:
                # Single season show - auto-select
                season_list = [season_details[0]["season"]]
                seasons_requested = str(season_details[0]["season"])
            else:
                # Multi-season show with no selection - reject
                raise ToolError(
                    f"This show has {len(season_details)} seasons. "
                    "Please specify which seasons to request (e.g., seasons=\"1,2\" or seasons=\"all\")"
                )

        result = await client.request_media(mt, tmdb_id, seasons=season_list)

        response = {
            "success": True,
            "request_id": result.id,
            "title": title,
            "year": year,
            "type": result.type.value,
            "status": result.status.name,
            "message": f"Request created for '{title}' (ID: {result.id})",
        }
        if seasons_requested:
            response["seasons_requested"] = seasons_requested

        return response
    except OverseerrError as e:
        raise ToolError(f"Request failed: {str(e)}")
    except ValueError as e:
        raise ToolError(f"Invalid input: {str(e)}")
    except Exception as e:
        raise ToolError(f"Unexpected error: {str(e)}")


@mcp.tool()
async def health_check() -> dict:
    """Check Overseerr server status and connectivity.

    Verifies the MCP server can connect to Overseerr.

    Returns:
        Server status and version information
    """
    try:
        client = get_client()
        status = await client.get_status()

        return {
            "status": "healthy",
            "overseerr": {
                "version": status.get("version"),
                "update_available": status.get("updateAvailable", False),
            },
        }
    except OverseerrError as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@mcp.tool()
async def get_media_status(
    tmdb_id: int,
    media_type: str,
) -> dict:
    """Check the availability status of a movie or TV show.

    Use search_media first to find the TMDB ID, then check its detailed status.
    Returns whether media is available, being processed, or needs to be requested.

    Args:
        tmdb_id: TMDB ID of the movie or TV show (from search results)
        media_type: "movie" or "tv"

    Returns:
        Status information including:
        - status: Numeric status code (1=Unknown, 2=Requested, 3=Processing, 4=Partially Available, 5=Available)
        - status_text: Human-readable status like "Available" or "Processing"
        - has_request: Whether any request exists for this media
        - request_status: Status of existing request ("Pending", "Approved", "Declined")
        - seasons_count: (TV only) Total number of seasons
    """
    try:
        client = get_client()
        mt = MediaType(media_type.lower())

        result = await client.get_media_status(tmdb_id, mt)
        return result

    except OverseerrError as e:
        raise ToolError(f"Status check failed: {str(e)}")
    except ValueError as e:
        raise ToolError(f"Invalid input: {str(e)}")
    except Exception as e:
        raise ToolError(f"Unexpected error: {str(e)}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Overseerr MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8080")),
        help="Port for HTTP transport (default: 8080)",
    )

    args = parser.parse_args()

    logger.info(f"Starting Overseerr MCP server with {args.transport} transport")

    if args.transport == "stdio":
        mcp.run()
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port, stateless_http=True)
    elif args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port, stateless_http=True)


if __name__ == "__main__":
    main()
