"""
Main entry point for the Esports Tournament Operations Manager environment.
"""
import uvicorn
from server.app import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8001,
        log_level="info"
    )