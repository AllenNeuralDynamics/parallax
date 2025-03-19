import logging
import json
import asyncio
import threading
from PyQt5.QtCore import QObject, pyqtSlot
from aiohttp import web

from .stage_controller import StageController

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class StageHttpServer(QObject):
    """Manages the Stage HTTP Server using aiohttp (Fully Async)"""

    def __init__(self, model, stages_info, port=8081):
        super().__init__()
        self.model = model
        self.stage_controller = StageController(self.model)
        self.stages_info = stages_info  # JSON data to be served
        self.port = port

        # Start Async Server in a Background Thread
        self.loop = asyncio.new_event_loop()
        self.server_thread = threading.Thread(target=self.run_event_loop, daemon=True)
        self.server_thread.start()

    def run_event_loop(self):
        """Runs the asyncio event loop in a separate thread"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.start_server())
        self.loop.run_forever()

    async def start_server(self):
        """Start the aiohttp server"""
        app = web.Application()
        app.router.add_get("/", self.handle_get)
        app.router.add_put("/", self.handle_put)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", self.port)
        await site.start()

        logger.info(f"Async HTTP server running on http://localhost:{self.port}")

    async def handle_get(self, request):
        """Handle GET request asynchronously"""
        return web.json_response(self.stages_info)

    async def handle_put(self, request):
        """Handle PUT request asynchronously and immediately process the command"""
        try:
            data = await request.json()
            logger.info(f"PUT request received:\n{json.dumps(data, indent=2)}")

            # Directly send command to StageController, overlapping previous requests
            #asyncio.to_thread(self.stage_controller.request, data)
            self.stage_controller.request(data)  # Process the command immediately

            return web.Response(text="Move request sent successfully")

        except json.JSONDecodeError:
            logger.error("Invalid JSON received in PUT request")
            return web.Response(status=400, text="Bad Request: Invalid JSON format")

