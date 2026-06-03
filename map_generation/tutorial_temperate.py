from map_generation.builder import MapBuilder


def generate(game_map):
    b = MapBuilder(game_map)
    b.resize(13, 13)

    b.zone(range(0, 13), biome='temperate')

    # Light scatter of forest and hills
    b.scatter('forest', biome='temperate', density=0.25)
    b.scatter('hills',  biome='temperate', density=0.15)

    # Iron on some hill tiles
    b.scatter('iron', density=0.30, requires='hills')

    # Spawn points at the four corners
    # rows, cols = b._map.rows, b._map.cols
    # for r, c in [(0, 0), (0, cols - 1), (rows - 1, 0), (rows - 1, cols - 1)]:
    #     tile = b._map.tiles[r][c]
    #     if 'spawn_point' not in tile.terrain_features:
    #         tile.terrain_features = list(tile.terrain_features) + ['spawn_point']
    rows, cols = b._map.rows, b._map.cols
    tile = b._map.tiles[rows - 1][cols - 1]
    if 'spawn_point' not in tile.terrain_features:
        tile.terrain_features = list(tile.terrain_features) + ['spawn_point']
