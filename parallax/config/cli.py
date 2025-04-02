"""
Parallax CLI Configuration
"""
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Parallax: A GUI application for controlling hardware devices.")

    parser.add_argument(
        "-d",
        "--dummy",
        action="store_true",
        help="Dummy mode for testing without hardware",
    )

    parser.add_argument(
        "-b",
        "--bundle_adjustment",
        action="store_true",
        help="Enable bundle adjustment feature",
    )

    return parser.parse_args()
