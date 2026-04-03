"""
Main entry point for the Esports Tournament Operations Manager environment.
"""
import os
import uvicorn
from server.app import app

if __name__ == "__main__":
    # Use same configuration as server/app.py for consistency
    PORT = int(os.getenv("PORT", "7860"))  # HF Spaces use 7860
    HOST = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        workers=1,  # Single worker for in-memory state consistency
        log_level="info"
    )