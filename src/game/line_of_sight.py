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

    def get_visible(self):
        """Returns None (all visible), set() (none visible), or a set of (row, col) tuples."""
        if self.mode == 'all':
            return None
        if self.mode == 'none':
            return set()
        # faction mode: computed later
        return None
