from map_generation.builder import MapBuilder


def generate(game_map):
    b = MapBuilder(game_map)
    b.resize(12, 14)

    b.zone(range(0, 2),  biome='coastal')    # water border
    b.zone(range(2, 7),  biome='temperate')
    b.zone(range(7, 12), biome='arid')

    b.blend_border('coastal',   'temperate')
    b.blend_border('temperate', 'arid')
    b.scatter_biome('coastal', density=0.02)

    # Temperate: heavy forest, light hills
    b.scatter('forest', biome='temperate', density=0.35)
    b.scatter('hills',  biome='temperate', density=0.20)

    # Arid: heavy hills, some mountains
    b.scatter('mountain', biome='arid', density=0.10)
    b.scatter('mountain', biome='arid', density=0.10, requires_neighbor='mountain')
    b.scatter('hills', biome='arid', density=0.30, requires_neighbor='mountain')
    b.scatter('hills', biome='arid', density=0.15)

    # Iron on 20% of hill tiles (both zones)
    b.scatter('iron', density=0.30, requires='hills')
