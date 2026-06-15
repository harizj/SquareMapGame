BABYLON_CITY_NAMES = [
    'Babylon', 'Nippur', 'Kish', 'Sippar', 'Uruk', 'Ur', 'Lagash',
    'Eridu', 'Akkad', 'Adab', 'Umma', 'Girsu', 'Eshnunna', 'Isin',
    'Larsa', 'Mari', 'Dur-Kurigalzu',
]

ASSYRIA_CITY_NAMES = [
    'Assur', 'Nineveh', 'Calah', 'Arbela', 'Arrapha', 'Khorsabad',
    'Dur-Sharrukin', 'Ekallatum', 'Imgur-Enlil', 'Tarbisu',
]


ROHAN_CITY_NAMES = [
    'Edoras', 'Aldburg', 'Dunharrow', 'Underharrow', 'Upbourn',
    'Snowbourn', 'Grimslade', 'Entwade', 'Harrowdale', 'Westfold',
    'Eastfold', 'Hornburg', 'Deeping Coomb', 'Langstrand', 'Calembel',
    'Ethring', 'Erelas', 'Nardol', 'Amon Din', 'Eilenach',
]

ISENGARD_CITY_NAMES = [
    'Isengard', 'Pliska', 'Preslav', 'Ohrid', 'Sredets',
    'Varna', 'Tarnovo', 'Lovech', 'Shumen', 'Silistra',
    'Vidin', 'Sozopol', 'Nesebar', 'Anchialos', 'Devnya',
    'Madara', 'Provat', 'Odesos', 'Melnik', 'Cherven',
]


COLORS_BLUE = {'dark': (35, 65, 150), 'light': (180, 210, 255)}
COLORS_RED  = {'dark': (125, 28, 30), 'light': (225, 148, 140)}

COLOR_SETS     = {'blue': COLORS_BLUE, 'red': COLORS_RED}
CITY_NAME_SETS = {
    'babylon':  BABYLON_CITY_NAMES,
    'assyria':  ASSYRIA_CITY_NAMES,
    'rohan':    ROHAN_CITY_NAMES,
    'isengard': ISENGARD_CITY_NAMES,
}


class Faction:
    def __init__(self, name, colors, city_names, director=None):
        from src.game.notification_log import NotificationLog
        self.name = name
        self.colors = colors  # dict with keys: 'dark', 'light'
        self.city_names = city_names
        self._city_name_idx = 0
        self.director = director  # None = player controlled
        self.notification_log = NotificationLog()

    @property
    def is_player_controlled(self):
        return self.director is None

    def do_turn(self, game_map, turn):
        if self.director is not None:
            self.director.director_moves(self, game_map)
            self.director.spawn_tick(self, game_map, turn)

    def take_city_name(self):
        name = self.city_names[self._city_name_idx % len(self.city_names)]
        self._city_name_idx += 1
        return name


