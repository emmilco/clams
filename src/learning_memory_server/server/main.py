"""Main entry point for the Learning Memory Server."""

import structlog

logger = structlog.get_logger()


def main() -> None:
    """Entry point for the MCP server."""
    logger.info("learning_memory_server.starting")
    # MCP server initialization will be implemented in future tasks
    logger.info("learning_memory_server.placeholder")


if __name__ == "__main__":
    main()
