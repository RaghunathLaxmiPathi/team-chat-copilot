"""Run the service: python -m app"""
import uvicorn

from app.config import Settings
from app.main import create_app

if __name__ == "__main__":
    settings = Settings.from_env()
    # access_log is off: the server's own access lines include query strings (which hold the token on /ws).
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, access_log=False, log_config=None)
