import logging
import json
from PyQt5.QtCore import QObject, QThread, pyqtSlot
from http.server import BaseHTTPRequestHandler, HTTPServer

from .stage_controller import StageController

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Server(HTTPServer):
    """Custom HTTPServer class"""
    def __init__(self, address, request_handler, stages_info, stage_controller):
        self.stages_info = stages_info
        self.stage_controller = stage_controller 
        super().__init__(address, request_handler)


class RequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests"""
    def log_message(self, format, *args):
        """Override to suppress default logging"""
        return  # Do nothing, suppressing logs

    def do_GET(self):
        """Handle GET request by returning JSON stage info"""
        try:
            response = json.dumps(self.server.stages_info, indent=4)  # Convert dictionary to JSON
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response.encode("utf-8"))
        except ConnectionAbortedError:
            logger.warning("Client disconnected before receiving full response.")
        except BrokenPipeError:
            logger.warning("Broken pipe: Client closed connection before response was sent.")
        except Exception as e:
            logger.error(f"Unexpected error in do_GET: {e}")


    def do_PUT(self):
        """Handle PUT request with JSON data"""
        content_length = int(self.headers.get('Content-Length', 0))

        if content_length == 0:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Bad Request: No content received")
            return

        try:
            put_data = self.rfile.read(content_length)  # Read request body
            json_data = json.loads(put_data.decode("utf-8"))  # Parse JSON

            logger.info(f"PUT request received: {json.dumps(json_data, indent=2)}")

            # Call the move_request function from stage_controller
            self.server.stage_controller.request(json_data)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Move request processed successfully")

        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Bad Request: Invalid JSON format")
            logger.error("Invalid JSON received in PUT request")


class HttpServerThread(QThread):
    """Threaded HTTP Server to avoid blocking the PyQt application"""

    def __init__(self, address, port, stages_info, stage_controller):
        super().__init__()
        self.server_address = (address, port)
        self.stages_info = stages_info
        self.stage_controller = stage_controller

    def run(self):
        """Start the HTTP server"""
        http_server = Server(self.server_address, RequestHandler, self.stages_info, self.stage_controller)
        logger.info(f"Starting HTTP server on {self.server_address[0]}:{self.server_address[1]}")
        try:
            http_server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            http_server.server_close()
            logger.info("Server stopped.")


class StageHttpServer(QObject):
    """Manages the Stage HTTP Server"""

    def __init__(self, model, stages_info, port=8081):
        super().__init__()
        self.model = model
        self.stage_controller = StageController(self.model)
        self.stages_info = stages_info  # JSON data to be served
        self.port = port
        self.server_thread = HttpServerThread("localhost", self.port, self.stages_info, self.stage_controller)
        self.server_thread.start()


    @pyqtSlot()
    def update_stages_info(self, new_info):
        """Update the JSON data served by the HTTP server"""
        self.stages_info.update(new_info)
        pass