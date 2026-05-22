from map_generation.builder import MapBuilder


def generate(game_map):
    b = MapBuilder(game_map)
    b.resize(12, 14)

    b.zone(range(0, 12), biome='temperate')

    # Mountain seed at center
    b.scatter('forest', rows=[5,6], cols=[6,7], density=1.0)

    # Expand the mountain cluster outward two rings
    b.scatter('forest', density=0.80, requires_neighbor='forest')
    b.scatter('forest', density=0.80, requires_neighbor='forest')
    b.scatter('forest', density=0.80, requires_neighbor='forest')

    # Light temperate features (land tiles only)
    b.scatter('hills',  biome='temperate', density=0.20)
    b.scatter('iron', density=0.30, requires='hills')
