from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from apps.scheduler.app_control import ApplicationControlService, ManagedProcess


class ApplicationControlServiceTests(SimpleTestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        scripts = root / ".venv" / "Scripts"
        scripts.mkdir(parents=True)
        (scripts / "python.exe").write_text("", encoding="utf-8")
        (scripts / "pythonw.exe").write_text("", encoding="utf-8")
        (root / "manage.py").write_text("", encoding="utf-8")
        (root / "run_server.py").write_text("", encoding="utf-8")
        self.service = ApplicationControlService(project_root=root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    @mock.patch("apps.scheduler.app_control.subprocess.run")
    def test_status_snapshot_classifies_web_and_qcluster(self, run_mock):
        payload = json.dumps(
            [
                {
                    "ProcessId": 10,
                    "ParentProcessId": 0,
                    "CommandLine": r"C:\ferias\.venv\Scripts\pythonw.exe run_server.py",
                },
                {
                    "ProcessId": 12,
                    "ParentProcessId": 10,
                    "CommandLine": r'"C:\Users\gabriel.caetano\AppData\Local\Programs\Python\Python312\pythonw.exe" run_server.py',
                },
                {
                    "ProcessId": 11,
                    "ParentProcessId": 0,
                    "CommandLine": r"C:\ferias\.venv\Scripts\pythonw.exe manage.py qcluster",
                },
                {
                    "ProcessId": 13,
                    "ParentProcessId": 11,
                    "CommandLine": r'"C:\Users\gabriel.caetano\AppData\Local\Programs\Python\Python312\pythonw.exe" manage.py qcluster',
                },
            ]
        )
        run_mock.return_value = mock.Mock(returncode=0, stdout=payload)

        status = self.service.status_snapshot()

        self.assertTrue(status.web_running)
        self.assertTrue(status.qcluster_running)
        self.assertEqual(status.overall_label, "Rodando")
        self.assertEqual([item.pid for item in status.web_processes], [12])
        self.assertEqual([item.pid for item in status.qcluster_processes], [13])

    @mock.patch.object(ApplicationControlService, "_is_port_in_use", return_value=False)
    @mock.patch.object(ApplicationControlService, "_spawn_hidden")
    @mock.patch.object(ApplicationControlService, "status_snapshot")
    @mock.patch("apps.scheduler.app_control.platform.system", return_value="Windows")
    def test_start_system_starts_only_missing_components(
        self,
        _platform_mock,
        status_mock,
        spawn_mock,
        _port_mock,
    ):
        status_mock.return_value = mock.Mock(web_running=False, qcluster_running=True)

        ok, message = self.service.start_system()

        self.assertTrue(ok)
        self.assertIn("aplicação web", message)
        spawn_mock.assert_called_once_with(["run_server.py"])

    @mock.patch.object(ApplicationControlService, "_spawn_hidden")
    @mock.patch.object(ApplicationControlService, "_find_process_on_port")
    @mock.patch.object(ApplicationControlService, "_is_port_in_use", return_value=True)
    @mock.patch.object(ApplicationControlService, "status_snapshot")
    @mock.patch("apps.scheduler.app_control.platform.system", return_value="Windows")
    def test_start_system_reports_port_conflict(
        self,
        _platform_mock,
        status_mock,
        _port_mock,
        find_process_mock,
        spawn_mock,
    ):
        status_mock.return_value = mock.Mock(web_running=False, qcluster_running=False)
        find_process_mock.return_value = ManagedProcess(
            pid=4321,
            command_line="pythonw.exe run_server.py",
        )

        ok, message = self.service.start_system()

        self.assertFalse(ok)
        self.assertIn("porta 8000", message)
        self.assertIn("PID: 4321", message)
        self.assertEqual(self.service.last_port_conflict, find_process_mock.return_value)
        spawn_mock.assert_not_called()

    @mock.patch.object(ApplicationControlService, "_is_port_in_use", return_value=False)
    @mock.patch.object(ApplicationControlService, "_kill_pid")
    def test_stop_port_conflict_kills_conflicting_process(self, kill_mock, _port_mock):
        self.service.last_port_conflict = ManagedProcess(
            pid=9876,
            command_line="pythonw.exe external_server.py",
        )

        ok, message = self.service.stop_port_conflict()

        self.assertTrue(ok)
        self.assertIn("porta 8000 liberada", message)
        kill_mock.assert_called_once_with(9876)
        self.assertIsNone(self.service.last_port_conflict)
