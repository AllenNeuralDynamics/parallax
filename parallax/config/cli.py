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
        "--dummy",
        action="store_true",
        help="Dummy mode for testing without hardware",
    )

    parser.add_argument(
        "--num_mock_cameras",
        type=int,
        default=1,
        help="Number of mock cameras to simulate (only valid if --dummy is set)",
    )

    parser.add_argument(
        "--bundle_adjustment",
        action="store_true",
        help="Enable bundle adjustment feature",
    )

    parser.add_argument(
        "--reticle_detection",
        choices=["default", "color_channel"],
        default="default",
        help="Choose the reticle detection algorithm version (e.g., 'default', 'color_channel').",
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode to visualize reticle and probe detection.",
    )

    return parser.parse_args()

def print_arg_info(args):
    """Print CLI argument selections for debugging."""
    if not args.dummy and args.num_mock_cameras != 1:
        print("\nWarning: --num-mock-cameras is only valid in dummy mode.")

    if args.dummy:
        print("\nRunning in dummy mode; hardware devices not accessible.")
        print(f"Simulating {args.num_mock_cameras} mock camera(s).")
    if args.bundle_adjustment:
        print("\nBundle adjustment feature enabled.")
    if args.test:
        print("\nTest mode to visualize reticle and probe detection.")
    if args.reticle_detection != "default":
        print(f"\nSelected reticle version: {args.reticle_detection}")
