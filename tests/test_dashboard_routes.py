import json
import shutil
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from pipeline import dashboard


class DashboardApiRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tempdir = (Path.cwd() / 'dashboard_test_runtime').resolve()
        shutil.rmtree(cls.tempdir, ignore_errors=True)
        cls.tempdir.mkdir(parents=True, exist_ok=True)
        cls.runtime = dashboard.DashboardRuntime(cls.tempdir)
        dashboard.DashboardHandler.runtime = cls.runtime
        dashboard._SYSTEM_STATUS_CACHE['cached_at'] = 0.0
        dashboard._SYSTEM_STATUS_CACHE['value'] = None
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), dashboard.DashboardHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.server.shutdown()
            cls.server.server_close()
        finally:
            cls.runtime.module_worker_stop.set()
            cls.runtime.model_reaper_stop.set()
            shutil.rmtree(cls.tempdir, ignore_errors=True)

    def get_json(self, path: str):
        with urllib.request.urlopen(self.base_url + path, timeout=10) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read().decode('utf-8'))

    def test_system_and_status_include_api_metadata(self) -> None:
        system = self.get_json('/api/system')
        self.assertEqual(system['api_version'], '2026-04-07.1')
        self.assertIn('capabilities', system)
        self.assertIn('cpu', system)
        self.assertIn('ram', system)
        self.assertIn('processes', system)
        self.assertIn('model_plan', system)
        self.assertIn('sampled_at', system)

        status = self.get_json('/api/status')
        self.assertTrue(status['ok'])
        self.assertEqual(status['api_version'], '2026-04-07.1')
        self.assertIn('capabilities', status)
        self.assertFalse(status['running'])
        self.assertEqual(status['queue_depth'], 0)

    def test_ops_routes_are_available(self) -> None:
        queue = self.get_json('/api/queue')
        self.assertTrue(queue['ok'])
        self.assertIn('active_job', queue)
        self.assertIn('pending_jobs', queue)
        self.assertIn('queue_depth', queue)

        alerts = self.get_json('/api/alerts?limit=5')
        self.assertTrue(alerts['ok'])
        self.assertIn('items', alerts)

        capacity = self.get_json('/api/capacity?window=10')
        self.assertTrue(capacity['ok'])
        self.assertIn('window_runs', capacity)
        self.assertIn('success_rate_pct', capacity)
        self.assertIn('gpu_cost_usd', capacity)

        configs = self.get_json('/api/configs?limit=5')
        self.assertTrue(configs['ok'])
        self.assertIn('items', configs)

    def test_root_html_uses_versioned_static_assets(self) -> None:
        with urllib.request.urlopen(self.base_url + '/', timeout=10) as response:
            html = response.read().decode('utf-8')
        self.assertIn('/static/css/dashboard.css?v=', html)
        self.assertIn('/static/js/dashboard.js?v=', html)

    def test_status_recovers_stale_orphaned_run(self) -> None:
        run_id = 'run-stale-12345'
        history_item = {
            'run_id': run_id,
            'job_id': 'job-stale-1',
            'priority': 'normal',
            'started_at': '2026-04-06T18:54:21+00:00',
            'finished_at': '2026-04-07T03:20:36+00:00',
            'duration_sec': 30375.0,
            'queued_delay_sec': 5.0,
            'state': 'stopped',
            'exit_code': 15,
            'total_books': 10,
            'completed_books': 0,
            'success_books': 0,
            'failed_books': 0,
            'story_root': None,
            'evaluation_ready': False,
            'current_stage': 'stopped',
            'last_error': None,
            'config': {'count': 10, 'model_plan': 'balanced'},
        }
        stale_status = {
            'state': 'running',
            'total_books': 10,
            'completed_books': 0,
            'success_books': 0,
            'failed_books': 0,
            'current_book': 1,
            'current_attempt': 1,
            'current_stage': 'STORY:start',
            'last_story_root': None,
            'last_error': None,
            'pre_evaluation': None,
            'model_plan': 'balanced',
            'updated_at': '2026-04-06T18:54:29+00:00',
        }

        with self.runtime.lock:
            self.runtime.process = None
            self.runtime.active_job = {
                'job_id': 'job-stale-1',
                'run_id': run_id,
                'priority': 'normal',
                'payload': {'count': 10, 'model_plan': 'balanced'},
                'started_at': '2026-04-06T18:54:21+00:00',
                'started_at_ts': 1.0,
                'enqueued_at_ts': 0.0,
            }
            self.runtime.current_run_id = run_id
            self.runtime.current_run_started_at = 1.0
            self.runtime.current_run_started_iso = '2026-04-06T18:54:21+00:00'
            self.runtime.current_exit_code = None
            self.runtime.last_config = {'count': 10, 'model_plan': 'balanced'}
            self.runtime.history = [history_item]
            self.runtime._save_history()
            self.runtime._write_json_dict(self.runtime.status_file, stale_status)

        status = self.get_json('/api/status')
        self.assertTrue(status['ok'])
        self.assertFalse(status['running'])
        self.assertIsNone(status['active_job'])
        self.assertFalse(self.runtime.status_file.exists())
        self.assertEqual(self.runtime.current_exit_code, 15)


if __name__ == '__main__':
    unittest.main()
