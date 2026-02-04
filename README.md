# Overseerr MCP Server

MCP server for [Overseerr](https://overseerr.dev/) media request management. Enables AI assistants to search for media, view requests, and manage media requests through the Model Context Protocol.

## Features

- **Search media** - Find movies and TV shows by title
- **View requests** - List requests with user info, filter by time period or status
- **User management** - List users and view individual request histories
- **Request media** - Submit new movie/TV requests
- **User correlation** - Easily answer questions like "list all requests from the last week and who requested them"

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Overseerr instance with admin API key

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd plexrequest_mcp

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

```bash
docker compose up -d
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_media` | Search for movies/TV shows by title. Returns TMDB IDs needed for requests. |
| `get_requests` | List media requests with user info. Filter by `status` (pending/approved/declined) or `days` (last N days). |
| `get_users` | List all Overseerr users with request counts. |
| `get_user_requests` | Get all requests for a specific user by ID. |
| `request_media` | Submit a new media request using TMDB ID from search results. |
| `health_check` | Check Overseerr server connectivity and version. |

## Example Queries

Once connected to an MCP client, you can ask:

- "Search for The Matrix"
- "List all requests from the last week and who requested them"
- "Show me all pending requests"
- "What has user ID 5 requested?"
- "Request the movie with TMDB ID 603"

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
