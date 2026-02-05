# Overseerr MCP Server

MCP server for [Overseerr](https://overseerr.dev/) media request management. Enables AI assistants to search for media, view requests, and manage media requests through the Model Context Protocol.

## Features

- **Search media** - Find movies and TV shows by title with availability status
- **Media status** - Check if content is available, processing, or needs to be requested
- **View requests** - List requests with user info, filter by approval status, availability status, or time period
- **User management** - List users and view individual request histories
- **Request media** - Submit new requests with preview confirmation and per-season selection for TV shows
- **User correlation** - Easily answer questions like "list all requests from the last week and who requested them"

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Overseerr instance with admin API key

## Installation

### Docker (recommended)

```bash
docker pull ghcr.io/suckerfish/overseerr-mcp:latest
```

### From source

```bash
git clone https://github.com/suckerfish/overseerr-mcp.git
cd overseerr-mcp

# Create virtual environment and install dependencies
uv venv && uv pip install -e .
```

## Configuration

Copy `.env.example` to `.env` and configure:

```env
OVERSEERR_URL=http://your-overseerr-ip:5055
OVERSEERR_API_KEY=your-admin-api-key-here
```

**Important:** Use the admin API key from **Settings → General → API Key** in Overseerr (not a user-level key).

## Usage

### Local (stdio transport)

```bash
uv run python -m src.server
```

### HTTP transport (for Docker/remote)

```bash
uv run python -m src.server --transport streamable-http --host 0.0.0.0 --port 8080
```

### Docker

Pre-built images are available for `linux/amd64` and `linux/arm64`.

```bash
# Using docker compose (recommended)
docker compose up -d

# Or run directly
docker run -d \
  -e OVERSEERR_URL=http://your-overseerr:5055 \
  -e OVERSEERR_API_KEY=your-api-key \
  -p 8080:8080 \
  ghcr.io/suckerfish/overseerr-mcp:latest
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_media` | Search for movies/TV shows by title. Returns TMDB IDs, ratings, and availability status. |
| `get_media_status` | Check detailed availability status for a specific TMDB ID. Shows request status, media availability, and season count for TV. |
| `get_requests` | List media requests with user info. Filter by `status` (pending/approved), `media_status` (available/processing/unavailable/failed), or `days`. Use `show_all=true` to get all matches instead of the default 20. |
| `get_users` | List all Overseerr users with request counts. |
| `get_user_requests` | Get requests for a specific user. Filter by `media_status` (processing/available/etc). Default 20 results, use `show_all=true` for all. |
| `request_media` | Request media with preview confirmation. Shows title, overview, genres, rating before confirming. TV shows require season selection. |
| `health_check` | Check Overseerr server connectivity and version. |

## Example Queries

Once connected to an MCP client, you can ask:

- "Search for The Matrix" - shows availability status inline
- "Is Breaking Bad available?" - checks media status
- "List all requests from the last week and who requested them"
- "Show me all pending requests"
- "What requests are still processing?" - filters by media availability
- "What has user ID 5 requested?"
- "Request the movie The Matrix" - shows preview, requires confirmation
- "Request seasons 1-3 of Breaking Bad" - per-season TV requests

## MCP Client Configuration

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "overseerr": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.server"],
      "cwd": "/path/to/plexrequest_mcp"
    }
  }
}
```

### HTTP/Docker

```json
{
  "mcpServers": {
    "overseerr": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

## License

MIT
