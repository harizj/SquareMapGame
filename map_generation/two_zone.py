from map_generation.builder import MapBuilder


def generate(game_map):
    b = MapBuilder(game_map)
    b.resize(12, 12)

    b.zone(range(0, 2),  biome='coastal')    # water border
    b.zone(range(2, 7),  biome='temperate')
    b.zone(range(7, 12), biome='arid')

    # Temperate: heavy forest, light hills
    b.scatter('forest', biome='temperate', density=0.40)
    b.scatter('hills',  biome='temperate', density=0.15)

    # Arid: heavy hills, some mountains
    b.scatter('hills',    biome='arid', density=0.25)
    b.scatter('mountain', biome='arid', density=0.20)

    # Iron on 20% of hill tiles (both zones)
    b.scatter('iron', density=0.20, requires='hills')
