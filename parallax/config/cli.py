"""
Parallax CLI Configuration
"""
import argparse

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parallax: A GUI application for acute in vivo acute electrophysiology experiments.",
        prog="python -m parallax",
    )

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

    parser.add_argument(
        "-r",
        "--reticle_detection",
        choices=["default", "color_channel"],
        default="default",
        help="Choose the reticle detection algorithm version (e.g., 'default', 'color_channel').",
    )
    return parser.parse_args()

def print_arg_info(args):
    """Print CLI argument selections for debugging."""
    if args.dummy:
        print("\nRunning in dummy mode; hardware devices not accessible.")
    if args.bundle_adjustment:
        print("\nBundle adjustment feature enabled.")
    if args.reticle_detection != "default":
        print(f"\nSelected reticle version: {args.reticle_detection}")
