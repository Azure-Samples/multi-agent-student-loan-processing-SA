import logging
import sys


def configure_logging(level: str = "INFO"):
    """
    Configure logging for MCP server.
    IMPORTANT: When using stdio transport, all logs must go to stderr
    to avoid interfering with MCP protocol communication on stdout.
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    ))
    
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[handler],
        force=True  # Override any existing configuration
    )

