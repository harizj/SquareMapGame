from map_generation.builder import MapBuilder


def generate(game_map):
    b = MapBuilder(game_map)
    b.resize(12, 14)

    b.zone(range(0, 12), biome='arid')

    # Mountain seed at center
    b.scatter('mountain', rows=[5,6], cols=[6,7], density=1.0)

    # Expand the mountain cluster outward two rings
    b.scatter('mountain', density=0.30, requires_neighbor='mountain')
    b.scatter('hills', density=0.35, requires_neighbor='mountain')
    b.scatter('hills', density=0.35, requires_neighbor='hills')

    # Light temperate features (land tiles only)
    b.scatter('hills',  biome='arid', density=0.05)
    b.scatter('forest', biome='arid', density=0.10)
    b.scatter('forest', biome='arid', density=0.20, requires_neighbor='forest')
    
    b.scatter('iron', density=0.20, requires='hills')
