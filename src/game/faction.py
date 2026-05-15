BABYLON_CITY_NAMES = [
    'Babylon', 'Nippur', 'Kish', 'Sippar', 'Uruk', 'Ur', 'Lagash',
    'Eridu', 'Akkad', 'Adab', 'Umma', 'Girsu', 'Eshnunna', 'Isin',
    'Larsa', 'Mari', 'Dur-Kurigalzu',
]

ASSYRIA_CITY_NAMES = [
    'Assur', 'Nineveh', 'Calah', 'Arbela', 'Arrapha', 'Khorsabad',
    'Dur-Sharrukin', 'Ekallatum', 'Imgur-Enlil', 'Tarbisu',
]


COLORS_BLUE = {'dark': (35, 65, 150), 'light': (180, 210, 255)}
COLORS_RED  = {'dark': (125, 28, 30), 'light': (225, 148, 140)}

COLOR_SETS     = {'blue': COLORS_BLUE, 'red': COLORS_RED}
CITY_NAME_SETS = {'babylon': BABYLON_CITY_NAMES, 'assyria': ASSYRIA_CITY_NAMES}


class Faction:
    def __init__(self, name, colors, city_names):
        self.name = name
        self.colors = colors  # dict with keys: 'dark', 'light'
        self.city_names = city_names
        self._city_name_idx = 0

    def take_city_name(self):
        name = self.city_names[self._city_name_idx % len(self.city_names)]
        self._city_name_idx += 1
        return name


