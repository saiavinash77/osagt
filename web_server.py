"""
Web server entry point.
Run with: python web_server.py
Or for production: uvicorn web_server:app --host 0.0.0.0 --port 8000
"""

from dotenv import load_dotenv
load_dotenv()

from src.config.settings import settings
from src.utils.logging_setup import configure_logging

configure_logging(settings.log_level, settings.log_file)

from src.web.api import app   # noqa: F401  (uvicorn needs this import)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "web_server:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
