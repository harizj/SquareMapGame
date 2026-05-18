class LineOfSight:
    """Controls which tiles are visible on the map.

    mode:
      'all'     -- all tiles visible (no fog)
      'none'    -- no tiles visible (full fog)
      'faction' -- only tiles visible to `faction`
    """

    def __init__(self):
        self.mode = 'all'
        self.faction = None
