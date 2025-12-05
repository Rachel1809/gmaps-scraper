import asyncio
import json
import os
import time
import platform
import subprocess
import argparse
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from worker import ScraperWorker
from pyngrok import ngrok
import uvicorn

# =============================================================================
# GLOBAL STATE & CONFIG
# =============================================================================
loop_ref = None
USE_NGROK = False

# =============================================================================
# UTILITIES
# =============================================================================
def force_kill_ngrok():
    """Aggressively kills system-wide ngrok processes."""
    system = platform.system()
    try:
        cmd = ["taskkill", "/F", "/IM", "ngrok.exe"] if system == "Windows" else ["pkill", "ngrok"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"⚠️ Process cleanup warning: {e}")

# =============================================================================
# CONNECTION MANAGER
# =============================================================================
class ConnectionManager:
    """
    Manages WebSocket connections and maps them to specific ScraperWorkers.
    Supports Multi-User isolation.
    """
    def __init__(self):
        self.active_connections: dict[WebSocket, ScraperWorker] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = None

    def disconnect(self, websocket: WebSocket):
        worker = self.active_connections.get(websocket)
        if worker:
            print("🔌 Stopping worker for disconnected user...")
            worker.stop()
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    def set_worker(self, websocket: WebSocket, worker: ScraperWorker):
        # Stop existing worker if present
        old_worker = self.active_connections.get(websocket)
        if old_worker:
            old_worker.stop()
        self.active_connections[websocket] = worker

    def get_worker(self, websocket: WebSocket) -> ScraperWorker:
        return self.active_connections.get(websocket)

    async def send_private_message(self, message: dict, websocket: WebSocket):
        """Sends data ONLY to the specific user's socket."""
        try:
            await websocket.send_text(json.dumps(message))
        except RuntimeError:
            pass  # Socket closed

    async def handle_command(self, websocket: WebSocket, command: dict):
        """Processes incoming JSON commands from the frontend."""
        action = command.get("action")
        
        if action == "start":
            self._handle_start(websocket, command)
        elif action == "stop":
            self._handle_stop(websocket)

    def _handle_start(self, websocket: WebSocket, command: dict):
        current_worker = self.get_worker(websocket)
        if current_worker and current_worker.is_running:
            current_worker.stop()
            time.sleep(0.5)

        keyword = command.get("keyword", "")
        headless = command.get("headless", False)
        ignore_urls = command.get("ignore_urls", [])

        # Notify UI
        asyncio.create_task(self.send_private_message({"type": "status", "payload": "RUNNING"}, websocket))
        log_msg = f"> Resuming '{keyword}'..." if ignore_urls else f"> Starting '{keyword}'..."
        asyncio.create_task(self.send_private_message({"type": "log", "payload": log_msg}, websocket))

        # Create Thread-Safe Callback
        def user_callback(event_type, payload):
            if loop_ref and loop_ref.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.send_private_message({"type": event_type, "payload": payload}, websocket), 
                    loop_ref
                )

        # Init & Start Worker
        new_worker = ScraperWorker(keyword, headless, user_callback, ignore_urls)
        self.set_worker(websocket, new_worker)
        new_worker.start()

    def _handle_stop(self, websocket: WebSocket):
        worker = self.get_worker(websocket)
        if worker:
            worker.stop()
            asyncio.create_task(self.send_private_message({"type": "status", "payload": "STOPPED"}, websocket))
            asyncio.create_task(self.send_private_message({"type": "log", "payload": "> Stop requested."}, websocket))

manager = ConnectionManager()

# =============================================================================
# LIFESPAN & APP SETUP
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global loop_ref
    loop_ref = asyncio.get_running_loop()
    
    print("\n==================================================================")
    print(f"🚀 SERVER MODE: {'NGROK (Public)' if USE_NGROK else 'LOCALHOST (Private)'}")
    
    if USE_NGROK:
        try:
            force_kill_ngrok()
            ngrok.kill()
            time.sleep(2)
            public_url = ngrok.connect("127.0.0.1:8000").public_url
            print(f"🌍 PUBLIC URL: {public_url}")
        except Exception as e:
            print(f"⚠️ Ngrok Failed: {e}. Falling back to Localhost.")
    else:
        print("🏠 LOCAL URL: http://127.0.0.1:8000")
    print("==================================================================\n")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down...")
    for ws, worker in manager.active_connections.items():
        if worker: worker.stop()
    
    if USE_NGROK:
        ngrok.kill()
        force_kill_ngrok()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            command = json.loads(data)
            await manager.handle_command(websocket, command)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"Socket Error: {e}")
        manager.disconnect(websocket)

# =============================================================================
# STATIC FILES & ENTRY
# =============================================================================
frontend_dist = os.path.join(os.path.dirname(__file__), "../frontend/dist")

if os.path.exists(frontend_dist):
    # Mount assets (JS/CSS)
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    # Serve Index (SPA Entry Point)
    @app.get("/")
    async def serve_spa():
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    print("⚠️  Frontend build not found. Run 'npm run build' in frontend/ to serve UI.")

if __name__ == "__main__":
    # Use argparse for robust CLI argument parsing
    parser = argparse.ArgumentParser(description="G-Maps Scraper Backend Server")
    parser.add_argument("--ngrok", action="store_true", help="Enable public access via Ngrok tunnel")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    
    args = parser.parse_args()
    
    if args.ngrok:
        USE_NGROK = True
        
    uvicorn.run(app, host=args.host, port=args.port)