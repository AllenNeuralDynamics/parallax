"""
This module provides a StageHttpServer class that manages an HTTP server for controlling
and querying the state of a stage controller. It uses aiohttp for asynchronous handling of HTTP requests.
"""

import asyncio
import json
import logging
import threading

from aiohttp import web

from .stage_controller import StageController

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class StageHttpServer:
    """Manages the Stage HTTP Server using aiohttp (Fully Async)"""

    def __init__(self, model, port=8081):
        """Initialize the StageHttpServer with a model, stages_info, and port."""
        super().__init__()
        self.model = model
        self.stage_controller = StageController(self.model)
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

        logger.debug(f"Async HTTP server running on http://localhost:{self.port}")

    async def handle_get(self, request):
        """
        Handle GET request asynchronously.
        Returns the current state of all stages including physical data and calibration.
        """
        try:
            # 1. Gather all stages from the model
            stages_output = {}
            # Use the same logic as your snapshot to gather data on-demand
            for sn in self.model.get_list_of_stage_sns():
                stage_obj = self.model.get_stage(sn)
                session = self.model.session.stages.get(sn)

                if stage_obj:
                    # Construct the nested hierarchy: SN -> obj, is_calib, calib_info
                    stages_output[sn] = {
                        "obj": stage_obj.model_dump(),
                        "is_calib": session.is_calib if session else False,
                        "calib_info": session.calib_info.model_dump() if session and session.calib_info else None,
                    }

            # 2. Build final response structure
            info = {"status": "success", "selected_sn": self.model.get_selected_stage_sn(), "probes": stages_output}

            # 3. Return as JSON response
            # web.json_response automatically handles headers and serialization
            return web.json_response(info)

        except Exception as e:
            logger.error(f"Error handling GET request: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def handle_put(self, request):
        """Handle PUT request asynchronously and immediately process the command"""
        try:
            data = await request.json()
            logger.info(f"PUT request received:\n{json.dumps(data, indent=2)}")

            # Offload CPU work to a thread
            loop = asyncio.get_running_loop()
            # Offload to thread pool executor
            result = await loop.run_in_executor(None, self.stage_controller.request, data)

            return web.Response(text=result)

        except json.JSONDecodeError:
            logger.error("Invalid JSON received in PUT request")
            return web.Response(status=400, text="Bad Request: Invalid JSON format")
