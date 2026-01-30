import uvicorn
import webbrowser
import threading
import time
import os
import sys

# Ensure main is in path
sys.path.append(os.path.join(os.path.dirname(__file__), "main"))

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    # Start browser in background
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run server
    print("Starting Chess Engine UI...")
    uvicorn.run("main.server.app:app", host="0.0.0.0", port=8000, reload=False)
