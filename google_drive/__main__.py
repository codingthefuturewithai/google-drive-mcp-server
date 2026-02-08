"""Main module for Google Drive MCP server.

This module allows the server to be run as a Python module using:
python -m google_drive

It delegates to the server application's main function.
"""

from google_drive.server.app import main

if __name__ == "__main__":
    main()