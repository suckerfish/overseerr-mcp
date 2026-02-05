"""Pydantic models for Overseerr API responses."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class MediaType(str, Enum):
    """Media type enumeration."""
    MOVIE = "movie"
    TV = "tv"


class RequestStatus(int, Enum):
    """Request status codes from Overseerr."""
    PENDING = 1
    APPROVED = 2
    DECLINED = 3


class MediaStatus(int, Enum):
    """Media availability status."""
    UNKNOWN = 1
    PENDING = 2
    PROCESSING = 3
    PARTIALLY_AVAILABLE = 4
    AVAILABLE = 5


def get_media_status_text(status: MediaStatus) -> str:
    """Get human-readable text for media status."""
    status_map = {
        MediaStatus.UNKNOWN: "Not Requested",
        MediaStatus.PENDING: "Requested",
        MediaStatus.PROCESSING: "Processing",
        MediaStatus.PARTIALLY_AVAILABLE: "Partially Available",
        MediaStatus.AVAILABLE: "Available",
    }
    return status_map.get(status, "Unknown")


class UserInfo(BaseModel):
    """User information."""
    model_config = ConfigDict(populate_by_name=True)

    id: int
    email: Optional[str] = None
    plexUsername: Optional[str] = None
    username: Optional[str] = None
    displayName: Optional[str] = Field(default=None, alias="displayName")
    avatar: Optional[str] = None
    requestCount: Optional[int] = None
    createdAt: Optional[datetime] = None

    @property
    def name(self) -> str:
        """Get the best available display name."""
        return self.displayName or self.plexUsername or self.username or self.email or f"User {self.id}"


class MediaSearchResult(BaseModel):
    """Search result for movies or TV shows."""
    id: int
    mediaType: MediaType
    title: Optional[str] = None  # For movies
    name: Optional[str] = None   # For TV shows
    originalTitle: Optional[str] = None
    originalName: Optional[str] = None
    overview: Optional[str] = None
    releaseDate: Optional[str] = None
    firstAirDate: Optional[str] = None
    posterPath: Optional[str] = None
    popularity: Optional[float] = None
    voteAverage: Optional[float] = None

    @property
    def display_title(self) -> str:
        """Get the display title regardless of media type."""
        return self.title or self.name or self.originalTitle or self.originalName or "Unknown"

    @property
    def year(self) -> Optional[str]:
        """Extract year from release date."""
        date = self.releaseDate or self.firstAirDate
        if date:
            return date[:4]
        return None


class MediaInfo(BaseModel):
    """Media information within a request."""
    id: int
    tmdbId: Optional[int] = None
    tvdbId: Optional[int] = None
    status: Optional[MediaStatus] = None
    mediaType: Optional[MediaType] = None


class MediaRequest(BaseModel):
    """A media request with user information."""
    id: int
    status: RequestStatus
    createdAt: datetime
    updatedAt: Optional[datetime] = None
    type: MediaType
    media: Optional[MediaInfo] = None
    requestedBy: Optional[UserInfo] = None
    modifiedBy: Optional[UserInfo] = None

    # These may be populated from expanded responses
    title: Optional[str] = None
    name: Optional[str] = None

    @property
    def display_title(self) -> str:
        """Get the display title."""
        return self.title or self.name or f"Media ID {self.media.tmdbId if self.media else 'Unknown'}"

    @property
    def requester_name(self) -> str:
        """Get the requester's display name."""
        if self.requestedBy:
            return self.requestedBy.name
        return "Unknown"

    @property
    def status_text(self) -> str:
        """Get human-readable status."""
        status_map = {
            RequestStatus.PENDING: "Pending",
            RequestStatus.APPROVED: "Approved",
            RequestStatus.DECLINED: "Declined",
        }
        return status_map.get(self.status, "Unknown")


class RequestsResponse(BaseModel):
    """Response from requests endpoint."""
    pageInfo: dict
    results: list[MediaRequest]


class RequestResponse(BaseModel):
    """Response from creating a request."""
    id: int
    status: RequestStatus
    createdAt: datetime
    type: MediaType
    media: Optional[MediaInfo] = None
    requestedBy: Optional[UserInfo] = None
