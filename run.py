import uvicorn
import subprocess
import sys

def check_requirements():
    try:
        import fastapi
        import uvicorn
        import aiosqlite
        import jinja2
        import multipart
    except ImportError:
        print("Missing requirements. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Requirements installed successfully.")

if __name__ == "__main__":
    check_requirements()
    
    # Run the uvicorn server
    print("Starting Smart Parking Backend...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
