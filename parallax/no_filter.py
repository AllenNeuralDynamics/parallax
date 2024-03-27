import time
from PyQt5.QtCore import pyqtSignal, QObject, QThread

class NoFilter(QObject):
    """Class representing no filter."""
    name = "None"
    frame_processed = pyqtSignal(object)

    class Worker(QObject):
        """Worker class for processing frames in a separate thread."""
        finished = pyqtSignal()
        frame_processed = pyqtSignal(object)

        def __init__(self, name):
            QObject.__init__(self)
            self.name = name
            self.running = True
            self.new = False

        def update_frame(self, frame):
            """Update the frame to be processed.
        
            Args:
                frame: The frame to be processed.
            """
            self.frame = frame
            self.new = True

        def process(self, frame):
            """Process nothing (no filter) and emit the frame_processed signal.
            Args:
                frame: The frame to be processed.
            """
            self.frame_processed.emit(frame)

        def stop_running(self):
            """Stop the worker from running."""
            self.running = False

        def start_running(self):
            """Start the worker running."""
            self.running = True

        def run(self):
            """Run the worker thread."""
            while self.running:
                if self.new:
                    self.process(self.frame)
                    self.new = False
                time.sleep(0.001)
            self.finished.emit()

    def __init__(self):
        """Initialize the filter object."""
        super().__init__()
        self.worker = None
        self.thread = None
        self.init_thread()

    def init_thread(self):
        # Initialize or reinitialize the worker and thread
        self.thread = QThread()
        self.worker = self.Worker(self.name)
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.worker.frame_processed.connect(self.frame_processed.emit)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(lambda: self.thread_deleted)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()

    def process(self, frame):
        """Process the frame using the worker.
    
        Args:
            frame: The frame to be processed.
        """
        if self.worker is not None:
            self.worker.update_frame(frame)

    def start(self):
        """Start the filter by reinitializing and starting the worker and thread."""
        self.init_thread()  # Reinitialize and start the worker and thread

    def stop(self):
        """Stop the filter by stopping the worker."""
        if self.worker is not None:
            self.worker.stop_running()
    
    def clean(self):
        """Clean up the filter by stopping the worker and waiting for the thread to finish."""
        if self.worker is not None:
            self.worker.stop_running()
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait()

    def __del__(self):
        """Destructor for the filter object."""
        self.clean()

    def thread_deleted(self):
        """Placeholder method for when the thread is deleted."""
        pass