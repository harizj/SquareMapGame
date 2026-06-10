class Notification:
    def __init__(self, text, key=None, priority='Normal'):
        self.text = text
        self.key = key  # tuple for deduplication, e.g. ('idle_pops', 'CityName')
        self.priority = priority


class NotificationLog:
    def __init__(self):
        self._notifications = []

    def add(self, text, key=None, priority='Normal'):
        """Add a notification. If key given and already present, skip."""
        if key and any(n.key == key for n in self._notifications):
            return
        self._notifications.append(Notification(text, key, priority))

    def remove(self, key):
        """Remove notification(s) matching key (call when condition resolves)."""
        self._notifications = [n for n in self._notifications if n.key != key]

    def remove_notification(self, notification):
        """Remove a specific notification by identity (used by dismiss button)."""
        self._notifications = [n for n in self._notifications if n is not notification]

    def clear(self):
        self._notifications.clear()

    @property
    def messages(self):
        return list(self._notifications)

    @property
    def count(self):
        return len(self._notifications)
