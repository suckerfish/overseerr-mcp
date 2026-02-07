"""Pydantic models for Plex API responses."""

from typing import Optional
from pydantic import BaseModel


class PlexLibrarySection(BaseModel):
    """A Plex library section (e.g., Movies, TV Shows)."""
    key: str
    title: str
    type: str  # "movie" or "show"


class PlexMediaItem(BaseModel):
    """A media item from the Plex library."""
    title: str
    year: Optional[int] = None
    rating: Optional[float] = None
    summary: Optional[str] = None
    content_rating: Optional[str] = None
    media_type: str  # "movie" or "tv" (normalized from Plex's "show")
