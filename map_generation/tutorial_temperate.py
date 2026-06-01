from map_generation.builder import MapBuilder


def generate(game_map):
    b = MapBuilder(game_map)
    b.resize(8, 10)

    b.zone(range(2, 8), biome='temperate')

    # Light scatter of forest and hills
    b.scatter('forest', biome='temperate', density=0.25)
    b.scatter('hills',  biome='temperate', density=0.15)

    # Iron on some hill tiles
    b.scatter('iron', density=0.30, requires='hills')
