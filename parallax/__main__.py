"""
Parallax: A GUI application for controlling hardware devices.
"""
import atexit
from PyQt5.QtWidgets import QApplication
from .main_window import MainWindow
from .model import Model
from .config.config_path import setup_logging, PARALLAX_ASCII
from .config.cli import parse_args, print_arg_info


# Main function to run the Parallax application
if __name__ == "__main__":
    # Print the ASCII art
    print(PARALLAX_ASCII)

    # Parse command line arguments
    args = parse_args()
    print_arg_info(args)

    # Set up logging
    setup_logging()

    # Initialize the Qt application
    app = QApplication([])

    # Initialize the model
    model = Model(
        version="V2",
        dummy=args.dummy,
        bundle_adjustment=args.bundle_adjustment
    )
    main_window = MainWindow(model, dummy=args.dummy)  # main window

    main_window.show()
    app.exec()

    # Clean up on exit
    atexit.register(model.clean)
    atexit.register(main_window.save_user_configs)
