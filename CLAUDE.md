# CLAUDE.md

## Project Overview

Overseerr MCP server - provides media request management capabilities via the Model Context Protocol.

## Tech Stack

- **Framework**: FastMCP 2.x
- **Package Manager**: uv
- **HTTP Client**: aiohttp (async)
- **Validation**: Pydantic v2
- **Deployment**: Docker with streamable-http transport

## Project Structure

```
src/
├── server.py              # FastMCP server, tool definitions
├── models/
│   └── overseerr.py       # Pydantic models for API responses
└── tools/
    └── overseerr_client.py # Async Overseerr API client
```

## Key Patterns

### Tool Registration
```python
@mcp.tool()
async def tool_name(param: str) -> dict:
    """Docstring becomes tool description."""
    client = get_client()
    # ... implementation
```

### Error Handling
```python
from fastmcp.exceptions import ToolError

try:
    result = await client.some_method()
except OverseerrError as e:
    raise ToolError(f"Failed: {str(e)}")
```

### Transport Configuration
- Local: `mcp.run()` (stdio)
- Docker: `mcp.run(transport="streamable-http", host="0.0.0.0", port=8080, stateless_http=True)`

## API Notes

- Overseerr requires URL encoding for search queries with spaces
- API key must be the admin key from Settings → General (not user-level keys)
- The API key is used verbatim (not base64 decoded)
- Datetime comparisons need timezone handling (API returns timezone-aware)

## Running Tests

```bash
# Quick client test
uv run python -c "
import asyncio
from dotenv import load_dotenv
load_dotenv()
from src.tools.overseerr_client import OverseerrClient

async def test():
    client = OverseerrClient()
    status = await client.get_status()
    print(f'Connected: v{status[\"version\"]}')
    await client.close()

asyncio.run(test())
"
```

## Common Tasks

### Add a new tool
1. Add method to `src/tools/overseerr_client.py`
2. Add Pydantic models if needed in `src/models/overseerr.py`
3. Register tool in `src/server.py` with `@mcp.tool()` decorator

### Update dependencies
```bash
uv add <package>
uv lock
```
