from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from apps.scheduler.app_control import ApplicationControlService


class ApplicationControlServiceTests(SimpleTestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        scripts = root / ".venv" / "Scripts"
        scripts.mkdir(parents=True)
        (scripts / "python.exe").write_text("", encoding="utf-8")
        (scripts / "pythonw.exe").write_text("", encoding="utf-8")
        self.service = ApplicationControlService(project_root=root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    @mock.patch("apps.scheduler.app_control.subprocess.run")
    def test_status_snapshot_classifies_web_and_qcluster(self, run_mock):
        payload = json.dumps(
            [
                {"ProcessId": 10, "CommandLine": r"C:\ferias\.venv\Scripts\pythonw.exe run_server.py"},
                {"ProcessId": 11, "CommandLine": r"C:\ferias\.venv\Scripts\pythonw.exe manage.py qcluster"},
            ]
        )
        run_mock.return_value = mock.Mock(returncode=0, stdout=payload)

        status = self.service.status_snapshot()

        self.assertTrue(status.web_running)
        self.assertTrue(status.qcluster_running)
        self.assertEqual(status.overall_label, "Rodando")
        self.assertEqual([item.pid for item in status.web_processes], [10])
        self.assertEqual([item.pid for item in status.qcluster_processes], [11])

    @mock.patch.object(ApplicationControlService, "_spawn_hidden")
    @mock.patch.object(ApplicationControlService, "status_snapshot")
    @mock.patch("apps.scheduler.app_control.platform.system", return_value="Windows")
    def test_start_system_starts_only_missing_components(self, _platform_mock, status_mock, spawn_mock):
        status_mock.return_value = mock.Mock(web_running=False, qcluster_running=True)

        ok, message = self.service.start_system()

        self.assertTrue(ok)
        self.assertIn("aplicação web", message)
        spawn_mock.assert_called_once_with(["run_server.py"])
