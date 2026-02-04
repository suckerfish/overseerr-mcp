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
        List of matching movies/TV shows with TMDB IDs, titles, years, and ratings
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
                    "tmdb_id": r.id,
                    "title": r.display_title,
                    "year": r.year,
                    "type": r.mediaType.value,
                    "overview": (r.overview[:200] + "...") if r.overview and len(r.overview) > 200 else r.overview,
                    "rating": round(r.voteAverage, 1) if r.voteAverage else None,
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
    days: Optional[int] = None,
    limit: int = 50,
) -> dict:
    """Get media requests with user information.

    Lists all requests showing who requested what and when.
    Perfect for queries like "list all requests from the last week and who requested them".

    Args:
        status: Optional filter - "pending", "approved", or "declined"
        days: Optional - only show requests from the last N days
        limit: Maximum number of requests to return (default 50)

    Returns:
        List of requests with titles, requesters, and timestamps
    """
    try:
        client = get_client()

        status_filter = None
        if status:
            status_map = {
                "pending": RequestStatus.PENDING,
                "approved": RequestStatus.APPROVED,
                "declined": RequestStatus.DECLINED,
            }
            status_filter = status_map.get(status.lower())

        since = None
        if days:
            since = datetime.now() - timedelta(days=days)

        requests = await client.get_requests_with_media_info(
            status=status_filter,
            since=since,
            take=limit,
        )

        return {
            "filter": {
                "status": status,
                "days": days,
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
async def get_user_requests(user_id: int) -> dict:
    """Get all requests made by a specific user.

    Shows all media requests from a particular user.
    Get the user_id from the get_users tool.

    Args:
        user_id: The Overseerr user ID

    Returns:
        User info and their request history
    """
    try:
        client = get_client()
        result = await client.get_user_requests(user_id)
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
) -> dict:
    """Request a movie or TV show to be added to Plex.

    Use search_media first to find the TMDB ID for the content you want.

    Args:
        tmdb_id: TMDB ID of the movie or TV show (from search results)
        media_type: "movie" or "tv"
        seasons: For TV shows - comma-separated season numbers (e.g., "1,2,3") or omit for all seasons

    Returns:
        Request confirmation with status
    """
    try:
        client = get_client()

        mt = MediaType(media_type.lower())

        season_list = None
        if seasons and mt == MediaType.TV:
            season_list = [int(s.strip()) for s in seasons.split(",")]

        result = await client.request_media(mt, tmdb_id, seasons=season_list)

        return {
            "success": True,
            "request_id": result.id,
            "status": result.status.name,
            "type": result.type.value,
            "message": f"Request created successfully (ID: {result.id})",
        }
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
