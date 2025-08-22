import sys
import pytest

# Import the functions under test from your __main__.py
from parallax.__main__ import parse_args, print_arg_info


def run_parse(monkeypatch, argv_tail):
    """Run parse_args() with a controlled argv (no -m / module bits)."""
    monkeypatch.setattr(sys, "argv", ["parallax", *argv_tail])
    return parse_args()



def test_defaults(monkeypatch, capsys):
    args = run_parse(monkeypatch, [])
    assert args.dummy is False
    assert args.nCameras == 1
    assert args.bundle_adjustment is False
    assert args.reticle_detection == "default"
    assert args.test is False

    print_arg_info(args)
    out = capsys.readouterr().out
    # Defaults should not print anything except potential warnings (none here)
    assert "dummy mode" not in out
    assert "Bundle adjustment" not in out
    assert "Test mode" not in out
    assert "Selected reticle version" not in out


def test_dummy_with_cameras_and_flags(monkeypatch, capsys):
    args = run_parse(monkeypatch, ["--dummy", "--nCameras", "3", "--bundle_adjustment", "--test"])
    assert args.dummy is True
    assert args.nCameras == 3
    assert args.bundle_adjustment is True
    assert args.test is True

    print_arg_info(args)
    out = capsys.readouterr().out
    assert "Running in dummy mode" in out
    assert "Simulating 3 mock camera(s)" in out
    assert "Bundle adjustment feature enabled" in out
    assert "Test mode to visualize reticle and probe detection" in out


def test_reticle_detection_color_channel(monkeypatch, capsys):
    args = run_parse(monkeypatch, ["--reticle_detection", "color_channel"])
    assert args.reticle_detection == "color_channel"

    print_arg_info(args)
    out = capsys.readouterr().out
    assert "Selected reticle version: color_channel" in out


def test_invalid_reticle_detection_value_exits(monkeypatch):
    # argparse should reject invalid choices with SystemExit
    with pytest.raises(SystemExit):
        run_parse(monkeypatch, ["--reticle_detection", "not-a-valid-choice"])


def test_warning_when_nCameras_without_dummy(monkeypatch, capsys):
    # nCameras != 1 while not in dummy mode should emit a warning
    args = run_parse(monkeypatch, ["--nCameras", "2"])
    assert args.dummy is False
    assert args.nCameras == 2

    print_arg_info(args)
    out = capsys.readouterr().out
    # Note: message uses '--num-mock-cameras' in your code text; assert substring safely
    assert "only valid in dummy mode" in out


def test_help_message_shows_and_exits(monkeypatch, capsys):
    # Asking for --help should exit with SystemExit(0) and print usage text
    with pytest.raises(SystemExit) as ei:
        run_parse(monkeypatch, ["--help"])
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "Parallax: A GUI application" in out
    assert "--dummy" in out
    assert "--nCameras" in out
    assert "--bundle_adjustment" in out
    assert "--reticle_detection" in out
    assert "--test" in out
