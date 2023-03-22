import os, json, argparse

package_path = os.path.split(os.path.dirname(__file__))[0]

# global configuration
config = {
    "views": [{}, {}],
    "cameras": [],
    "stages": [],
    "mock_sim": {
        "show_checkers": True,
        "show_axes": True,
        "auto_select_corr_points": True,
    },
    "calibration_path": "./",
    "console_history_file": os.path.join(package_path, 'console.log'),
    "console_edit_command": "code -g {fileName}:{lineNum}",
}


def parse_cli_args():
    parser = argparse.ArgumentParser(prog='parallax')
    parser.add_argument('--config', type=str, default=None, help='configuration file to load at startup')
    args = parser.parse_args()
    return args


def init_config(args):
    global config
    if args.config is not None:
        loaded_config = json.load(open(args.config, 'r'))
        for k,v in loaded_config.items():
            if k not in config:
                raise KeyError(f"Invalid config key {k}")
            config[k] = v

def post_init_config(model, main_window):
    for i,view in enumerate(config['views']):
        screen_widget = main_window.widget.add_screen()
        if 'default_camera' in view:
            camera = model.get_camera(view['default_camera'])
            screen_widget.set_camera(camera)
