class Notification:
    def __init__(self, text, key=None):
        self.text = text
        self.key = key  # tuple for deduplication, e.g. ('idle_pops', 'CityName')


class NotificationLog:
    def __init__(self):
        self._notifications = []

    def add(self, text, key=None):
        """Add a notification. If key given and already present, skip."""
        if key and any(n.key == key for n in self._notifications):
            return
        self._notifications.append(Notification(text, key))

    def remove(self, key):
        """Remove notification(s) matching key (call when condition resolves)."""
        self._notifications = [n for n in self._notifications if n.key != key]

    def clear(self):
        self._notifications.clear()

    @property
    def messages(self):
        return list(self._notifications)

    @property
    def count(self):
        return len(self._notifications)
