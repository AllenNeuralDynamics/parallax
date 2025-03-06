import logging
import json
from PyQt5.QtCore import QObject, QThread, pyqtSlot
from http.server import BaseHTTPRequestHandler, HTTPServer

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Server(HTTPServer):
    """Custom HTTPServer class"""
    def __init__(self, address, request_handler, stages_info):
        self.stages_info = stages_info  # Stage data
        super().__init__(address, request_handler)


class RequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests"""

    def do_GET(self):
        """Handle GET request by returning JSON stage info"""
        response = json.dumps(self.server.stages_info, indent=4)  # Convert dictionary to JSON
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response.encode("utf-8"))
        logger.info("GET request received")


class HttpServerThread(QThread):
    """Threaded HTTP Server to avoid blocking the PyQt application"""

    def __init__(self, address, port, stages_info):
        super().__init__()
        self.server_address = (address, port)
        self.stages_info = stages_info

    def run(self):
        """Start the HTTP server"""
        http_server = Server(self.server_address, RequestHandler, self.stages_info)
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

    def __init__(self, stages_info, stage_controller, port=8081):
        super().__init__()
        self.stages_info = stages_info  # JSON data to be served
        self.stage_controller = stage_controller
        self.port = port
        self.server_thread = HttpServerThread("localhost", self.port, self.stages_info)
        self.server_thread.start()

    @pyqtSlot()
    def update_stages_info(self, new_info):
        """Update the JSON data served by the HTTP server"""
        self.stages_info.update(new_info)
        pass
