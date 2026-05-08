import json
import os

_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
SAVES_DIR = os.path.normpath(os.path.join(_BASE, 'saved_maps'))


def save_map(game_map, name):
    os.makedirs(SAVES_DIR, exist_ok=True)
    path = os.path.join(SAVES_DIR, f"{name}.json")
    with open(path, 'w') as f:
        json.dump(game_map.to_dict(), f, indent=2)
    return path


def load_map_data(name):
    path = os.path.join(SAVES_DIR, f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)
