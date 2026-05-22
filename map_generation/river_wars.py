from map_generation.builder import MapBuilder


def generate(game_map):
    b = MapBuilder(game_map)
    b.resize(12, 14)

    b.zone(range(0, 1), biome='desert')
    b.zone(range(1, 11), biome='temperate')
    b.zone(range(11, 12), biome='desert')
    b.blend_border('temperate', 'desert')

    # Two rivers dividing the map into three zones
    b.generate_river(row=3)
    b.generate_river(row=8)

    # Terrain features
    b.scatter('hills',  biome='temperate', density=0.05)
    b.scatter('hills',  biome='temperate', density=0.10, requires_neighbor='hills')
    b.scatter('forest', biome='temperate', density=0.15)
    b.scatter('forest', biome='temperate', density=0.20, requires_neighbor='forest')
    
    b.scatter('iron', density=0.50, requires='hills')