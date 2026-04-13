"""
MORBION — BaseView
All process views inherit from this.
Defines the update(data) contract.
"""

from PyQt6.QtWidgets import QWidget


class BaseView(QWidget):

    def __init__(self, rest_client, parent=None):
        super().__init__(parent)
        self._rest = rest_client

    def update_data(self, data: dict):
        """
        Called on every WS push with this process's data dict.
        data is always a complete dict — online=False if unreachable.
        Subclass implements this. Never raises.
        """
        raise NotImplementedError