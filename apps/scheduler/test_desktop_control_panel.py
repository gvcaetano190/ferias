from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase

from desktop_control_panel import ControlPanelApp


class ControlPanelQuitTests(SimpleTestCase):
    def test_quit_app_stops_services_and_closes_panel(self) -> None:
        app = ControlPanelApp.__new__(ControlPanelApp)
        app.service = mock.Mock()
        app.root = mock.Mock()
        icon = mock.Mock()

        app.quit_app(icon=icon)

        icon.stop.assert_called_once_with()
        app.service.stop_system.assert_called_once_with()
        app.root.after.assert_called_once_with(0, app.root.destroy)

    def test_quit_app_without_icon_still_stops_services(self) -> None:
        app = ControlPanelApp.__new__(ControlPanelApp)
        app.service = mock.Mock()
        app.root = mock.Mock()

        app.quit_app(icon=None)

        app.service.stop_system.assert_called_once_with()
        app.root.after.assert_called_once_with(0, app.root.destroy)
