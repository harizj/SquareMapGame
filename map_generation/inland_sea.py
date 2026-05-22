from map_generation.builder import MapBuilder


def generate(game_map):
    b = MapBuilder(game_map)
    b.resize(12, 14)

    b.zone(range(0, 12), biome='temperate')

    # 2x2 coastal seed at center
    b.zone([4, 7], biome='coastal', cols=[6])

    # Expand the lake outward two rings
    b.scatter_biome('coastal', density=0.75, requires_neighbor='coastal')
    b.scatter_biome('coastal', density=0.60, requires_neighbor='coastal')

    # Light temperate features
    b.scatter('hills',  biome='temperate', density=0.10)
    b.scatter('hills', biome='temperate', density=0.10, requires_neighbor='hills')
    b.scatter('forest', biome='temperate', density=0.10)
    b.scatter('forest', biome='temperate', density=0.10, requires_neighbor='forest')
    b.scatter('iron', density=0.30, requires='hills')
