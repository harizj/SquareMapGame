from map_generation.builder import MapBuilder

_CARDINAL = [(0, -1), (0, 1), (-1, 0), (1, 0)]


def generate(game_map):
    b = MapBuilder(game_map)
    b.resize(11, 11)

    b.zone(range(0, 11), biome='temperate')

    # Rivers along the left and right edges
    b.generate_river(0, 1, lanes=range(1, 4), direction='S')
    b.generate_river(10, 9, lanes=range(8, 10), direction='N')

    # Place a mountain at the map center
    center = b._map.tiles[5][5]
    center.terrain_features = list(center.terrain_features) + ['mountain']
    center.update_terrain_properties()
    center.build_deposits()

    # Light scatter of forest, hills, and mountains
    b.scatter('mountain', biome='temperate', density=0.5, requires_neighbor='mountain', neighbor_dirs=_CARDINAL)
    b.scatter('hills', biome='temperate', density=0.5, requires_neighbor='mountain', neighbor_dirs=_CARDINAL)
    b.scatter('hills', biome='temperate', density=0.05)
    b.scatter('hills', biome='temperate', density=0.25, requires_neighbor='hills', neighbor_dirs=_CARDINAL)

    b.scatter('forest', biome='temperate', density=0.15)
    b.scatter('forest', biome='temperate', density=0.5, requires_neighbor='forest', neighbor_dirs=_CARDINAL)

    # Iron on some hill tiles
    b.scatter('iron', density=0.5, requires='hills')

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
