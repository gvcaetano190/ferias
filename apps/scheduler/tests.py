from __future__ import annotations

import subprocess
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.scheduler.models import JobExecution, ScheduledJob, SchedulerRuntime
from apps.scheduler.services import SchedulerRunResult, SchedulerService


class SchedulerServiceTests(TestCase):
    def setUp(self):
        self.service = SchedulerService()

    def test_runtime_without_pid_is_not_reported_as_running(self):
        runtime = SchedulerRuntime.objects.create(
            singleton_key="default",
            process_id=None,
            last_status="RUNNING",
            last_message="Heartbeat antigo sem PID",
            last_heartbeat_at=timezone.now(),
        )

        status = self.service._runtime_status()
        runtime.refresh_from_db()

        self.assertFalse(status["is_running"])
        self.assertFalse(status["is_starting"])
        self.assertEqual(status["label"], "Parado")
        self.assertEqual(runtime.last_status, "STOPPED")

    def test_dashboard_reconciles_stale_running_execution_when_scheduler_is_down(self):
        started_at = timezone.now() - timedelta(minutes=1)
        job = ScheduledJob.objects.create(
            name="Job teste",
            job_type=ScheduledJob.JOB_TYPE_BLOCK,
            enabled=True,
            schedule_type=ScheduledJob.SCHEDULE_INTERVAL,
            interval_minutes=30,
            next_run_at=timezone.now(),
            last_status=ScheduledJob.STATUS_RUNNING,
        )
        execution = JobExecution.objects.create(
            job=job,
            started_at=started_at,
            status=JobExecution.STATUS_RUNNING,
            trigger_source=JobExecution.SOURCE_SCHEDULER,
        )
        SchedulerRuntime.objects.create(
            singleton_key="default",
            process_id=None,
            last_status="STOPPED",
            last_message="Scheduler offline",
            last_heartbeat_at=timezone.now() - timedelta(minutes=20),
        )

        data = self.service.dashboard_data()
        execution.refresh_from_db()
        job.refresh_from_db()

        self.assertEqual(data["summary"]["rodando"], 0)
        self.assertEqual(execution.status, JobExecution.STATUS_ERROR)
        self.assertIsNotNone(execution.finished_at)
        self.assertEqual(job.last_status, ScheduledJob.STATUS_ERROR)

    @patch("apps.scheduler.services.SchedulerService._is_process_alive", return_value=False)
    def test_force_stop_targets_lists_running_task_without_pid(self, process_alive_mock):
        job = ScheduledJob.objects.create(
            name="Job travado",
            job_type=ScheduledJob.JOB_TYPE_BLOCK,
            enabled=True,
            schedule_type=ScheduledJob.SCHEDULE_INTERVAL,
            interval_minutes=30,
            next_run_at=timezone.now(),
            last_status=ScheduledJob.STATUS_RUNNING,
        )
        execution = JobExecution.objects.create(
            job=job,
            started_at=timezone.now(),
            status=JobExecution.STATUS_RUNNING,
            trigger_source=JobExecution.SOURCE_MANUAL,
        )

        data = self.service.force_stop_targets()

        self.assertEqual(len(data["targets"]), 1)
        self.assertEqual(data["targets"][0]["execution_id"], execution.id)
        self.assertEqual(data["targets"][0]["mode"], "clear_record")

    @patch("apps.scheduler.services.SchedulerService._is_process_alive", return_value=True)
    def test_force_stop_targets_marks_live_scheduler_task_as_request_cancel(self, process_alive_mock):
        SchedulerRuntime.objects.create(singleton_key="default", process_id=999, last_status="RUNNING")
        job = ScheduledJob.objects.create(
            name="Job live",
            job_type=ScheduledJob.JOB_TYPE_BLOCK,
            enabled=True,
            schedule_type=ScheduledJob.SCHEDULE_INTERVAL,
            interval_minutes=30,
            next_run_at=timezone.now(),
            last_status=ScheduledJob.STATUS_RUNNING,
        )
        execution = JobExecution.objects.create(
            job=job,
            started_at=timezone.now(),
            status=JobExecution.STATUS_RUNNING,
            trigger_source=JobExecution.SOURCE_SCHEDULER,
        )

        data = self.service.force_stop_targets()

        self.assertEqual(data["targets"][0]["execution_id"], execution.id)
        self.assertEqual(data["targets"][0]["mode"], "request_cancel")

    @patch("apps.scheduler.services.SchedulerService._is_process_alive", return_value=False)
    def test_force_stop_execution_clears_stale_record_when_no_process_exists(self, process_alive_mock):
        job = ScheduledJob.objects.create(
            name="Job travado",
            job_type=ScheduledJob.JOB_TYPE_BLOCK,
            enabled=True,
            schedule_type=ScheduledJob.SCHEDULE_INTERVAL,
            interval_minutes=30,
            next_run_at=timezone.now(),
            last_status=ScheduledJob.STATUS_RUNNING,
        )
        execution = JobExecution.objects.create(
            job=job,
            started_at=timezone.now(),
            status=JobExecution.STATUS_RUNNING,
            trigger_source=JobExecution.SOURCE_SCHEDULER,
        )

        ok, message = self.service.force_stop_execution(execution.id)
        execution.refresh_from_db()
        job.refresh_from_db()

        self.assertTrue(ok)
        self.assertIn("encerrada", message.lower())
        self.assertEqual(execution.status, JobExecution.STATUS_ERROR)
        self.assertIsNotNone(execution.finished_at)
        self.assertEqual(job.last_status, ScheduledJob.STATUS_ERROR)

    @patch("apps.scheduler.services.SchedulerService._is_process_alive", return_value=True)
    def test_force_stop_execution_requests_cancel_without_stopping_service(self, process_alive_mock):
        runtime = SchedulerRuntime.objects.create(singleton_key="default", process_id=555, last_status="RUNNING")
        job = ScheduledJob.objects.create(
            name="Job live",
            job_type=ScheduledJob.JOB_TYPE_BLOCK,
            enabled=True,
            schedule_type=ScheduledJob.SCHEDULE_INTERVAL,
            interval_minutes=30,
            next_run_at=timezone.now(),
            last_status=ScheduledJob.STATUS_RUNNING,
        )
        execution = JobExecution.objects.create(
            job=job,
            started_at=timezone.now(),
            status=JobExecution.STATUS_RUNNING,
            trigger_source=JobExecution.SOURCE_SCHEDULER,
        )

        ok, message = self.service.force_stop_execution(execution.id)
        execution.refresh_from_db()
        job.refresh_from_db()
        runtime.refresh_from_db()

        self.assertTrue(ok)
        self.assertIn("permanece ativo", message.lower())
        self.assertTrue(execution.cancel_requested)
        self.assertIsNone(execution.finished_at)
        self.assertEqual(runtime.process_id, 555)
        self.assertEqual(job.last_status, ScheduledJob.STATUS_RUNNING)

    def test_ensure_default_jobs_includes_operational_block_verification(self):
        self.service.ensure_default_jobs()

        self.assertTrue(
            ScheduledJob.objects.filter(job_type=ScheduledJob.JOB_TYPE_VERIFY_BLOCK).exists()
        )

    def test_ensure_default_jobs_deduplicates_jobs_by_type(self):
        primary = ScheduledJob.objects.create(
            name="Verificação block",
            job_type=ScheduledJob.JOB_TYPE_BLOCK,
            enabled=True,
            schedule_type=ScheduledJob.SCHEDULE_INTERVAL,
            interval_minutes=30,
            next_run_at=timezone.now(),
            last_status=ScheduledJob.STATUS_IDLE,
        )
        duplicate = ScheduledJob.objects.create(
            name="Verificacao block",
            job_type=ScheduledJob.JOB_TYPE_BLOCK,
            enabled=True,
            schedule_type=ScheduledJob.SCHEDULE_INTERVAL,
            interval_minutes=15,
            next_run_at=timezone.now(),
            last_status=ScheduledJob.STATUS_ERROR,
        )
        execution = JobExecution.objects.create(
            job=duplicate,
            started_at=timezone.now(),
            status=JobExecution.STATUS_SUCCESS,
            trigger_source=JobExecution.SOURCE_MANUAL,
        )

        self.service.ensure_default_jobs()

        self.assertEqual(ScheduledJob.objects.filter(job_type=ScheduledJob.JOB_TYPE_BLOCK).count(), 1)
        execution.refresh_from_db()
        primary.refresh_from_db()
        self.assertEqual(execution.job_id, primary.id)
        self.assertEqual(primary.name, "Verificação block")
        self.assertEqual(primary.interval_minutes, 30)

    @patch("apps.scheduler.services.BlockService")
    def test_execute_job_accepts_verify_block_candidates_type(self, block_service_mock):
        job = ScheduledJob.objects.create(
            name="Verificação operacional block",
            job_type="verify_block_candidates",
            enabled=True,
            schedule_type=ScheduledJob.SCHEDULE_INTERVAL,
            interval_minutes=20,
            next_run_at=timezone.now(),
            last_status=ScheduledJob.STATUS_IDLE,
        )
        block_service_mock.return_value.processar_verificacao_operacional_block.return_value = {
            "summary_message": "ok",
        }

        result = self.service.execute_job(job)

        self.assertEqual(result.status, JobExecution.STATUS_SUCCESS)
        self.assertEqual(result.message, "ok")

    @patch("apps.scheduler.services.BlockService")
    def test_execute_job_skips_block_when_operational_queue_is_missing(self, block_service_mock):
        job = ScheduledJob.objects.create(
            name="Verificação block",
            job_type=ScheduledJob.JOB_TYPE_BLOCK,
            enabled=True,
            schedule_type=ScheduledJob.SCHEDULE_INTERVAL,
            interval_minutes=30,
            next_run_at=timezone.now(),
            last_status=ScheduledJob.STATUS_IDLE,
        )
        block_service_mock.return_value.processar_verificacao_block.return_value = {
            "skipped": True,
            "message": "aguardando fila operacional",
        }

        result = self.service.execute_job(job)

        self.assertEqual(result.status, JobExecution.STATUS_SKIPPED)
        self.assertIn("aguardando", result.message)

    @patch("apps.scheduler.services.SchedulerService.run_job")
    def test_run_due_jobs_processes_only_one_job_per_cycle_in_priority_order(self, run_job_mock):
        now = timezone.now()
        sync_job = ScheduledJob.objects.create(
            name="Sincronização da planilha",
            job_type=ScheduledJob.JOB_TYPE_SYNC,
            enabled=True,
            schedule_type=ScheduledJob.SCHEDULE_INTERVAL,
            interval_minutes=60,
            next_run_at=now - timedelta(minutes=5),
            last_status=ScheduledJob.STATUS_IDLE,
        )
        ScheduledJob.objects.create(
            name="Verificação operacional block",
            job_type=ScheduledJob.JOB_TYPE_VERIFY_BLOCK,
            enabled=True,
            schedule_type=ScheduledJob.SCHEDULE_INTERVAL,
            interval_minutes=20,
            next_run_at=now - timedelta(minutes=4),
            last_status=ScheduledJob.STATUS_IDLE,
        )
        ScheduledJob.objects.create(
            name="Verificação block",
            job_type=ScheduledJob.JOB_TYPE_BLOCK,
            enabled=True,
            schedule_type=ScheduledJob.SCHEDULE_INTERVAL,
            interval_minutes=30,
            next_run_at=now - timedelta(minutes=3),
            last_status=ScheduledJob.STATUS_IDLE,
        )
        run_job_mock.return_value = SchedulerRunResult(
            status=JobExecution.STATUS_SUCCESS,
            message="ok",
            payload={},
        )

        results = self.service.run_due_jobs()

        self.assertEqual(len(results), 1)
        run_job_mock.assert_called_once()
        called_job = run_job_mock.call_args.args[0]
        self.assertEqual(called_job.id, sync_job.id)

    @patch("apps.scheduler.services.time.sleep", return_value=None)
    @patch("apps.scheduler.services.SchedulerService._is_process_alive")
    @patch("apps.scheduler.services.subprocess.Popen")
    @patch("apps.scheduler.services.platform.system", return_value="Windows")
    def test_start_runtime_marks_starting_without_console_window(
        self,
        platform_mock,
        popen_mock,
        process_alive_mock,
        sleep_mock,
    ):
        runtime = SchedulerRuntime.objects.create(singleton_key="default")
        process = popen_mock.return_value
        process.pid = 4321
        process_alive_mock.side_effect = [False, True, True]

        ok, message = self.service.start_runtime()
        runtime.refresh_from_db()

        self.assertTrue(ok)
        self.assertIn("inicializacao", message.lower())
        self.assertEqual(runtime.process_id, 4321)
        self.assertEqual(runtime.last_status, "STARTING")
        _, kwargs = popen_mock.call_args
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertTrue(kwargs["creationflags"] >= 0)

    @patch("apps.scheduler.services.platform.system", return_value="Windows")
    @patch("apps.scheduler.services.subprocess.run")
    @patch("apps.scheduler.services.SchedulerService._is_process_alive")
    def test_stop_runtime_clears_running_tasks(self, process_alive_mock, subprocess_run_mock, platform_mock):
        runtime = SchedulerRuntime.objects.create(singleton_key="default", process_id=444, last_status="RUNNING")
        job = ScheduledJob.objects.create(
            name="Job live",
            job_type=ScheduledJob.JOB_TYPE_BLOCK,
            enabled=True,
            schedule_type=ScheduledJob.SCHEDULE_INTERVAL,
            interval_minutes=30,
            next_run_at=timezone.now(),
            last_status=ScheduledJob.STATUS_RUNNING,
        )
        execution = JobExecution.objects.create(
            job=job,
            started_at=timezone.now(),
            status=JobExecution.STATUS_RUNNING,
            trigger_source=JobExecution.SOURCE_SCHEDULER,
            cancel_requested=False,
        )
        subprocess_run_mock.return_value.returncode = 0
        subprocess_run_mock.return_value.stdout = ""
        subprocess_run_mock.return_value.stderr = ""
        process_alive_mock.side_effect = [True, False]

        ok, message = self.service.stop_runtime()
        execution.refresh_from_db()
        job.refresh_from_db()
        runtime.refresh_from_db()

        self.assertTrue(ok)
        self.assertIn("sucesso", message.lower())
        self.assertEqual(runtime.process_id, None)
        self.assertEqual(execution.status, JobExecution.STATUS_ERROR)
        self.assertIsNotNone(execution.finished_at)
        self.assertEqual(job.last_status, ScheduledJob.STATUS_ERROR)
