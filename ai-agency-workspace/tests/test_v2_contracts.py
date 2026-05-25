import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]


def load_module(name, relative_path):
    module_path = WORKSPACE / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


router = load_module("hq_router", "hq-backend/hq_router.py")
worker = load_module("worker_node", "branch-daemon/worker_node.py")
epic_manager = load_module("hq_epic_manager", "hq-backend/hq_epic_manager.py")
project_manager = load_module("hq_project_manager", "hq-backend/hq_project_manager.py")
issue_listener = load_module("hq_issue_listener", "hq-backend/hq_issue_listener.py")


class RouterContractTests(unittest.TestCase):
    def test_routes_qa_to_kent_branch_by_default(self):
        branch_id, payload = router.route_payload({
            "task_id": "qa-001",
            "type": "qa",
            "prompt": "write regression tests",
            "workspace_path": "/tmp/project",
        })

        self.assertEqual(branch_id, "branch_kent")
        self.assertEqual(payload["agent"], "Kent")
        self.assertEqual(payload["workspace_path"], "/tmp/project")
        self.assertIn("Persona: Kent", payload["prompt"])

    def test_rejects_unknown_task_type(self):
        with self.assertRaisesRegex(ValueError, "type must be one of"):
            router.validate_task({
                "task_id": "bad-001",
                "type": "marketing",
                "prompt": "ship it",
            })

    def test_rejects_bool_timeout(self):
        with self.assertRaisesRegex(ValueError, "timeout must be an integer"):
            router.validate_task({
                "task_id": "bad-002",
                "type": "backend",
                "prompt": "ship it",
                "timeout": True,
            })


class WorkerContractTests(unittest.TestCase):
    def test_branch_name_is_sanitized_and_never_empty(self):
        self.assertEqual(worker.build_task_branch_name("../"), "feature/task_unknown")
        self.assertEqual(worker.build_task_branch_name("abc/123"), "feature/task_abc-123")

    def test_parse_payload_rejects_bool_timeout(self):
        payload = json.dumps({
            "task_id": "bad-003",
            "agent": "Linus",
            "repo_path": ".",
            "prompt": "do work",
            "timeout": False,
        })

        with self.assertRaisesRegex(ValueError, "timeout must be an integer"):
            worker.parse_task_payload(payload)

    def test_parse_payload_preserves_base_branch(self):
        payload = json.dumps({
            "task_id": "chain-001",
            "agent": "Linus",
            "repo_path": ".",
            "prompt": "do work",
            "timeout": 1,
            "workspace_path": "/tmp/project",
            "base_branch": "feature/task_parent",
        })

        task = worker.parse_task_payload(payload)

        self.assertEqual(task["base_branch"], "feature/task_parent")

    def test_bouncer_blocks_forbidden_prompt(self):
        blocked, pattern = worker.check_bouncer_security("please run sudo now")
        self.assertTrue(blocked)
        self.assertEqual(pattern, r"\bsudo\b")

    def test_bouncer_scans_command_even_when_prompt_is_clean(self):
        # Regression: previously command was only scanned when prompt was empty,
        # so a benign prompt paired with a dangerous legacy command slipped past.
        with tempfile.TemporaryDirectory() as directory:
            response = worker.execute_task_with_git({
                "task_id": "bouncer-001",
                "agent": "Linus",
                "repo_path": ".",
                "prompt": "benign instruction",
                "timeout": 1,
                "command": "rm -rf /",
                "workspace_path": directory,
            })

        self.assertEqual(response["status"], "security_error")
        self.assertIn("Bouncer", response["stderr"])

    def test_missing_workspace_fails_before_git_or_cli(self):
        response = worker.execute_task_with_git({
            "task_id": "safe-001",
            "agent": "Linus",
            "repo_path": ".",
            "prompt": "do work",
            "timeout": 1,
            "command": "true",
            "workspace_path": "",
        })

        self.assertEqual(response["status"], "security_error")
        self.assertIn("workspace_path is missing", response["stderr"])

    def test_existing_non_git_workspace_returns_git_error(self):
        with tempfile.TemporaryDirectory() as directory:
            response = worker.execute_task_with_git({
                "task_id": "git-001",
                "agent": "Linus",
                "repo_path": ".",
                "prompt": "do work",
                "timeout": 1,
                "command": "true",
                "workspace_path": directory,
            })

        self.assertEqual(response["status"], "git_error")
        self.assertIn("Git repository", response["stderr"])


class EpicManagerContractTests(unittest.TestCase):
    def test_dispatches_only_ready_tasks_and_persists_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_paths = (
                epic_manager.EPIC_QUEUE_DIR,
                epic_manager.STATE_DIR,
                epic_manager.TASK_QUEUE_DIR,
                epic_manager.STATUS_DIR,
            )
            epic_manager.EPIC_QUEUE_DIR = root / "epic_queue"
            epic_manager.STATE_DIR = epic_manager.EPIC_QUEUE_DIR / ".state"
            epic_manager.TASK_QUEUE_DIR = root / "task_queue"
            epic_manager.STATUS_DIR = root / "status_log"
            try:
                epic_manager.ensure_directories()
                epic_path = epic_manager.EPIC_QUEUE_DIR / "build.json"
                epic_path.write_text(json.dumps([
                    {
                        "task_id": "task-a",
                        "type": "backend",
                        "prompt": "first",
                        "workspace_path": "/tmp/project",
                        "depends_on": [],
                    },
                    {
                        "task_id": "task-b",
                        "type": "backend",
                        "prompt": "second",
                        "workspace_path": "/tmp/project",
                        "depends_on": ["task-a"],
                    },
                ]), encoding="utf-8")

                epic_manager.run_once()

                self.assertTrue((epic_manager.TASK_QUEUE_DIR / "task_task-a.json").exists())
                self.assertFalse((epic_manager.TASK_QUEUE_DIR / "task_task-b.json").exists())

                (epic_manager.TASK_QUEUE_DIR / "task_task-a.json").unlink()
                epic_manager.run_once()
                self.assertFalse((epic_manager.TASK_QUEUE_DIR / "task_task-a.json").exists())

                status_path = epic_manager.STATUS_DIR / "task-a.json"
                status_path.write_text(json.dumps({
                    "task_id": "task-a",
                    "status": "success",
                    "branch_name": "feature/task_task-a",
                    "received_at": "2026-05-24T10:00:00+00:00",
                }), encoding="utf-8")
                epic_manager.run_once()
                task_b_path = epic_manager.TASK_QUEUE_DIR / "task_task-b.json"
                self.assertTrue(task_b_path.exists())
                task_b_payload = json.loads(task_b_path.read_text(encoding="utf-8"))
                self.assertEqual(task_b_payload["base_branch"], "feature/task_task-a")
            finally:
                (
                    epic_manager.EPIC_QUEUE_DIR,
                    epic_manager.STATE_DIR,
                    epic_manager.TASK_QUEUE_DIR,
                    epic_manager.STATUS_DIR,
                ) = old_paths

    def test_dispatch_uses_most_recent_dependency_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_paths = (
                epic_manager.EPIC_QUEUE_DIR,
                epic_manager.STATE_DIR,
                epic_manager.TASK_QUEUE_DIR,
                epic_manager.STATUS_DIR,
            )
            epic_manager.EPIC_QUEUE_DIR = root / "epic_queue"
            epic_manager.STATE_DIR = epic_manager.EPIC_QUEUE_DIR / ".state"
            epic_manager.TASK_QUEUE_DIR = root / "task_queue"
            epic_manager.STATUS_DIR = root / "status_log"
            try:
                epic_manager.ensure_directories()
                epic_path = epic_manager.EPIC_QUEUE_DIR / "chain.json"
                epic_path.write_text(json.dumps([
                    {
                        "task_id": "task-c",
                        "type": "backend",
                        "prompt": "third",
                        "workspace_path": "/tmp/project",
                        "depends_on": ["task-a", "task-b"],
                    },
                ]), encoding="utf-8")
                (epic_manager.STATUS_DIR / "task-a.json").write_text(json.dumps({
                    "task_id": "task-a",
                    "status": "success",
                    "branch_name": "feature/task_task-a",
                    "received_at": "2026-05-24T10:00:00+00:00",
                }), encoding="utf-8")
                (epic_manager.STATUS_DIR / "task-b.json").write_text(json.dumps({
                    "task_id": "task-b",
                    "status": "success",
                    "branch_name": "feature/task_task-b",
                    "received_at": "2026-05-24T10:05:00+00:00",
                }), encoding="utf-8")

                epic_manager.run_once()

                task_c_path = epic_manager.TASK_QUEUE_DIR / "task_task-c.json"
                task_c_payload = json.loads(task_c_path.read_text(encoding="utf-8"))
                self.assertEqual(task_c_payload["base_branch"], "feature/task_task-b")
            finally:
                (
                    epic_manager.EPIC_QUEUE_DIR,
                    epic_manager.STATE_DIR,
                    epic_manager.TASK_QUEUE_DIR,
                    epic_manager.STATUS_DIR,
                ) = old_paths


class ProjectManagerContractTests(unittest.TestCase):
    def _patch_dirs(self, root):
        old = (
            project_manager.PROJECT_QUEUE_DIR,
            project_manager.PROJECTS_DIR,
            project_manager.TASK_QUEUE_DIR,
            project_manager.EPIC_QUEUE_DIR,
            project_manager.STATUS_DIR,
            project_manager.PORTFOLIO_DIR,
        )
        project_manager.PROJECT_QUEUE_DIR = root / "project_queue"
        project_manager.PROJECTS_DIR = root / "projects"
        project_manager.TASK_QUEUE_DIR = root / "task_queue"
        project_manager.EPIC_QUEUE_DIR = root / "epic_queue"
        project_manager.STATUS_DIR = root / "status_log"
        project_manager.PORTFOLIO_DIR = root / "portfolio"
        project_manager.ensure_directories()
        return old

    def _restore_dirs(self, old):
        (
            project_manager.PROJECT_QUEUE_DIR,
            project_manager.PROJECTS_DIR,
            project_manager.TASK_QUEUE_DIR,
            project_manager.EPIC_QUEUE_DIR,
            project_manager.STATUS_DIR,
            project_manager.PORTFOLIO_DIR,
        ) = old

    def test_intake_creates_project_and_dispatches_spec_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = self._patch_dirs(root)
            try:
                intake_path = project_manager.PROJECT_QUEUE_DIR / "demo.intake.json"
                intake_path.write_text(json.dumps({
                    "name": "Login Module",
                    "ceo_brief": "Build a passwordless login.",
                    "workspace_path": "/tmp/project",
                }), encoding="utf-8")

                project_manager.run_once()

                # Intake archived.
                self.assertTrue((project_manager.PROJECT_QUEUE_DIR / "processed" / "demo.intake.json").exists())
                # Project dir + manifest exist.
                project_dirs = [p for p in project_manager.PROJECTS_DIR.iterdir() if p.is_dir()]
                self.assertEqual(len(project_dirs), 1)
                manifest = json.loads((project_dirs[0] / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["stage"], "spec")
                self.assertEqual(manifest["status"], "stage_in_progress")
                self.assertEqual(manifest["open_action"], "linus")
                self.assertIsNotNone(manifest["current_task_id"])
                # spec_review task queued for the router.
                task_files = list(project_manager.TASK_QUEUE_DIR.glob("task_*.json"))
                self.assertEqual(len(task_files), 1)
                payload = json.loads(task_files[0].read_text(encoding="utf-8"))
                self.assertEqual(payload["type"], "spec_review")
                self.assertEqual(payload["project_id"], project_dirs[0].name)
            finally:
                self._restore_dirs(old)

    def test_spec_with_open_questions_waits_on_ceo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = self._patch_dirs(root)
            try:
                intake = project_manager.PROJECT_QUEUE_DIR / "x.intake.json"
                intake.write_text(json.dumps({
                    "name": "X",
                    "ceo_brief": "test",
                    "workspace_path": "/tmp/x",
                }), encoding="utf-8")
                project_manager.run_once()
                project_dir = next(p for p in project_manager.PROJECTS_DIR.iterdir() if p.is_dir())
                manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
                task_id = manifest["current_task_id"]

                # Linus produces spec + open_questions, then status hits success.
                (project_dir / "spec.md").write_text("# Spec", encoding="utf-8")
                (project_dir / "open_questions.md").write_text("1. What auth?", encoding="utf-8")
                (project_manager.STATUS_DIR / f"{task_id}.json").write_text(
                    json.dumps({"task_id": task_id, "status": "success"}), encoding="utf-8"
                )

                project_manager.run_once()
                manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["status"], "awaiting_ceo_answers")
                self.assertEqual(manifest["open_action"], "ceo")
            finally:
                self._restore_dirs(old)

    def test_ceo_approval_flag_advances_to_next_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = self._patch_dirs(root)
            try:
                intake = project_manager.PROJECT_QUEUE_DIR / "y.intake.json"
                intake.write_text(json.dumps({
                    "name": "Y",
                    "ceo_brief": "test",
                    "workspace_path": "/tmp/y",
                }), encoding="utf-8")
                project_manager.run_once()
                project_dir = next(p for p in project_manager.PROJECTS_DIR.iterdir() if p.is_dir())
                manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
                spec_task_id = manifest["current_task_id"]

                # Clean spec success (no open questions).
                (project_dir / "spec.md").write_text("# Spec", encoding="utf-8")
                (project_manager.STATUS_DIR / f"{spec_task_id}.json").write_text(
                    json.dumps({"task_id": spec_task_id, "status": "success"}), encoding="utf-8"
                )
                project_manager.run_once()
                manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["status"], "stage_pending_approval")

                # CEO approves -> wireframe stage dispatched.
                (project_dir / "ceo_approval.flag").touch()
                project_manager.run_once()
                manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["stage"], "wireframe")
                self.assertEqual(manifest["status"], "stage_in_progress")
                self.assertNotEqual(manifest["current_task_id"], spec_task_id)
                self.assertFalse((project_dir / "ceo_approval.flag").exists())
            finally:
                self._restore_dirs(old)

    def test_failed_task_flags_board_meeting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = self._patch_dirs(root)
            try:
                intake = project_manager.PROJECT_QUEUE_DIR / "z.intake.json"
                intake.write_text(json.dumps({
                    "name": "Z",
                    "ceo_brief": "test",
                    "workspace_path": "/tmp/z",
                }), encoding="utf-8")
                project_manager.run_once()
                project_dir = next(p for p in project_manager.PROJECTS_DIR.iterdir() if p.is_dir())
                manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
                task_id = manifest["current_task_id"]

                (project_manager.STATUS_DIR / f"{task_id}.json").write_text(
                    json.dumps({"task_id": task_id, "status": "error"}), encoding="utf-8"
                )
                project_manager.run_once()
                manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["status"], "board_meeting")
                self.assertEqual(manifest["open_action"], "ceo")
            finally:
                self._restore_dirs(old)

    def _setup_project_at_poc(self, root):
        """Helper: create project, drive spec to completion, return (project_dir, manifest)."""
        old = self._patch_dirs(root)
        intake = project_manager.PROJECT_QUEUE_DIR / "poc.intake.json"
        intake.write_text(json.dumps({
            "name": "POC Project",
            "ceo_brief": "Build a POC.",
            "workspace_path": "/tmp/poc",
            "project_id": "poc-test-proj",
        }), encoding="utf-8")
        project_manager.run_once()
        project_dir = next(p for p in project_manager.PROJECTS_DIR.iterdir() if p.is_dir())
        manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))

        # Spec stage: mark success, approve.
        spec_task_id = manifest["current_task_id"]
        (project_dir / "spec.md").write_text("# Spec", encoding="utf-8")
        (project_manager.STATUS_DIR / f"{spec_task_id}.json").write_text(
            json.dumps({"task_id": spec_task_id, "status": "success", "agent": "Linus"}), encoding="utf-8"
        )
        project_manager.run_once()
        (project_dir / "ceo_approval.flag").touch()
        project_manager.run_once()
        manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
        # Now at wireframe stage; mark success + approve.
        wire_task_id = manifest["current_task_id"]
        (project_manager.STATUS_DIR / f"{wire_task_id}.json").write_text(
            json.dumps({"task_id": wire_task_id, "status": "success", "agent": "Pixel"}), encoding="utf-8"
        )
        project_manager.run_once()
        (project_dir / "ceo_approval.flag").touch()
        project_manager.run_once()
        manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
        # Now at poc stage.
        return old, project_dir, manifest

    def test_epic_stage_picks_up_decompose_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, project_dir, manifest = self._setup_project_at_poc(root)
            try:
                self.assertEqual(manifest["stage"], "poc")
                decompose_task_id = manifest["current_task_id"]

                # Linus produces poc_epic.json.
                epic_tasks = [
                    {"task_id": "poc-task-1", "type": "backend", "prompt": "build it",
                     "workspace_path": "/tmp/poc", "depends_on": []},
                    {"task_id": "poc-task-2", "type": "frontend", "prompt": "show it",
                     "workspace_path": "/tmp/poc", "depends_on": ["poc-task-1"]},
                ]
                (project_dir / "poc_epic.json").write_text(json.dumps(epic_tasks), encoding="utf-8")
                (project_manager.STATUS_DIR / f"{decompose_task_id}.json").write_text(
                    json.dumps({"task_id": decompose_task_id, "status": "success", "agent": "Linus"}),
                    encoding="utf-8",
                )

                project_manager.run_once()
                manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))

                self.assertEqual(manifest["status"], "stage_in_epic")
                self.assertEqual(manifest["current_epic_id"], f"{manifest['project_id']}_poc")
                self.assertIn("poc-task-1", manifest["current_epic_task_ids"])
                self.assertIn("poc-task-2", manifest["current_epic_task_ids"])
                epic_queue_file = project_manager.EPIC_QUEUE_DIR / f"{manifest['project_id']}_poc.json"
                self.assertTrue(epic_queue_file.exists(), "epic file must be in epic_queue")
            finally:
                self._restore_dirs(old)

    def test_epic_completion_flips_to_pending_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, project_dir, manifest = self._setup_project_at_poc(root)
            try:
                decompose_task_id = manifest["current_task_id"]
                epic_tasks = [
                    {"task_id": "poc-done-1", "type": "backend", "prompt": "x",
                     "workspace_path": "/tmp/poc", "depends_on": []},
                ]
                (project_dir / "poc_epic.json").write_text(json.dumps(epic_tasks), encoding="utf-8")
                (project_manager.STATUS_DIR / f"{decompose_task_id}.json").write_text(
                    json.dumps({"task_id": decompose_task_id, "status": "success", "agent": "Linus"}),
                    encoding="utf-8",
                )
                project_manager.run_once()

                # All epic tasks succeed.
                (project_manager.STATUS_DIR / "poc-done-1.json").write_text(
                    json.dumps({"task_id": "poc-done-1", "status": "success", "agent": "Linus"}),
                    encoding="utf-8",
                )
                project_manager.run_once()
                manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["status"], "stage_pending_approval")
            finally:
                self._restore_dirs(old)

    def test_epic_failed_task_flags_board_meeting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, project_dir, manifest = self._setup_project_at_poc(root)
            try:
                decompose_task_id = manifest["current_task_id"]
                epic_tasks = [
                    {"task_id": "poc-fail-1", "type": "backend", "prompt": "x",
                     "workspace_path": "/tmp/poc", "depends_on": []},
                    {"task_id": "poc-fail-2", "type": "frontend", "prompt": "y",
                     "workspace_path": "/tmp/poc", "depends_on": []},
                ]
                (project_dir / "poc_epic.json").write_text(json.dumps(epic_tasks), encoding="utf-8")
                (project_manager.STATUS_DIR / f"{decompose_task_id}.json").write_text(
                    json.dumps({"task_id": decompose_task_id, "status": "success", "agent": "Linus"}),
                    encoding="utf-8",
                )
                project_manager.run_once()

                # First task succeeds, second fails.
                (project_manager.STATUS_DIR / "poc-fail-1.json").write_text(
                    json.dumps({"task_id": "poc-fail-1", "status": "success", "agent": "Linus"}),
                    encoding="utf-8",
                )
                (project_manager.STATUS_DIR / "poc-fail-2.json").write_text(
                    json.dumps({"task_id": "poc-fail-2", "status": "error", "agent": "Pixel"}),
                    encoding="utf-8",
                )
                project_manager.run_once()
                manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["status"], "board_meeting")
            finally:
                self._restore_dirs(old)

    def test_stage_pending_approval_dispatches_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = self._patch_dirs(root)
            # Patch BOARD_REPORTS_DIR too.
            old_board = project_manager.BOARD_REPORTS_DIR
            project_manager.BOARD_REPORTS_DIR = root / "board_reports"
            project_manager.BOARD_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            try:
                intake = project_manager.PROJECT_QUEUE_DIR / "rep.intake.json"
                intake.write_text(json.dumps({
                    "name": "Report Test",
                    "ceo_brief": "test report dispatch",
                    "workspace_path": "/tmp/rep",
                }), encoding="utf-8")
                project_manager.run_once()
                project_dir = next(p for p in project_manager.PROJECTS_DIR.iterdir() if p.is_dir())
                manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
                spec_task_id = manifest["current_task_id"]

                (project_dir / "spec.md").write_text("# Spec", encoding="utf-8")
                (project_manager.STATUS_DIR / f"{spec_task_id}.json").write_text(
                    json.dumps({"task_id": spec_task_id, "status": "success", "agent": "Linus"}),
                    encoding="utf-8",
                )
                project_manager.run_once()
                manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["status"], "stage_pending_approval")

                project_id = manifest["project_id"]
                report_tasks = [
                    f for f in project_manager.TASK_QUEUE_DIR.glob("task_*.json")
                    if "report" in f.name
                ]
                self.assertGreater(len(report_tasks), 0, "at least one report task must be queued")
                payload = json.loads(report_tasks[0].read_text(encoding="utf-8"))
                self.assertEqual(payload["type"], "report")
                self.assertIn(f"{project_id}_spec", payload["report_target"])
                # report_task_ids recorded in manifest.
                self.assertTrue(len(manifest.get("report_task_ids") or []) > 0)
            finally:
                project_manager.BOARD_REPORTS_DIR = old_board
                self._restore_dirs(old)

    def test_closing_project_dispatches_retros_per_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = self._patch_dirs(root)
            old_board = project_manager.BOARD_REPORTS_DIR
            project_manager.BOARD_REPORTS_DIR = root / "board_reports"
            project_manager.BOARD_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            try:
                # Build a minimal project and fast-forward to closed by writing
                # a manifest directly at closed status.
                pid = "retro-proj-01"
                project_dir = project_manager.PROJECTS_DIR / pid
                (project_dir / "issues").mkdir(parents=True, exist_ok=True)
                (project_dir / "retros").mkdir(parents=True, exist_ok=True)
                (project_dir / "wireframes").mkdir(parents=True, exist_ok=True)
                (project_dir / "decisions").mkdir(parents=True, exist_ok=True)
                (project_dir / "brief.md").write_text("# Brief", encoding="utf-8")

                task_a = f"{pid}-spec-aaa111"
                task_b = f"{pid}-wire-bbb222"
                # Fake status records with agent fields.
                (project_manager.STATUS_DIR / f"{task_a}.json").write_text(
                    json.dumps({"task_id": task_a, "status": "success", "agent": "Linus"}),
                    encoding="utf-8",
                )
                (project_manager.STATUS_DIR / f"{task_b}.json").write_text(
                    json.dumps({"task_id": task_b, "status": "success", "agent": "Pixel"}),
                    encoding="utf-8",
                )

                manifest = {
                    "project_id": pid,
                    "name": "Retro Test",
                    "ceo_brief": "test",
                    "workspace_path": "/tmp/retro",
                    "stage": "prod",
                    "status": "stage_pending_approval",
                    "open_action": "ceo",
                    "stage_history": [],
                    "task_history": [task_a, task_b],
                    "current_task_id": task_b,
                    "current_epic_id": None,
                    "current_epic_task_ids": [],
                    "report_task_ids": [],
                    "retro_task_ids": [],
                    "retros_dispatched": False,
                    "created_at": "2026-05-25T00:00:00+00:00",
                    "updated_at": "2026-05-25T00:00:00+00:00",
                }
                mpath = project_manager.PROJECTS_DIR / pid / "manifest.json"
                mpath.write_text(json.dumps(manifest), encoding="utf-8")

                # CEO approval flag triggers close.
                (project_dir / "ceo_approval.flag").touch()
                project_manager.run_once()

                manifest = json.loads(mpath.read_text(encoding="utf-8"))
                self.assertEqual(manifest["status"], "closed")
                self.assertTrue(manifest.get("retros_dispatched"))
                retro_task_ids = manifest.get("retro_task_ids") or []
                self.assertGreaterEqual(len(retro_task_ids), 2)

                retro_payloads = []
                for tid in retro_task_ids:
                    tf = project_manager.TASK_QUEUE_DIR / f"task_{tid}.json"
                    self.assertTrue(tf.exists(), f"retro task file {tf.name} must exist")
                    retro_payloads.append(json.loads(tf.read_text(encoding="utf-8")))

                agents = {p["agent_target"] for p in retro_payloads}
                self.assertIn("Linus", agents)
                self.assertIn("Pixel", agents)

                # Idempotent: second run_once must NOT add more retro tasks.
                task_count_before = len(list(project_manager.TASK_QUEUE_DIR.glob("task_*retro*.json")))
                project_manager.run_once()
                task_count_after = len(list(project_manager.TASK_QUEUE_DIR.glob("task_*retro*.json")))
                self.assertEqual(task_count_before, task_count_after)
            finally:
                project_manager.BOARD_REPORTS_DIR = old_board
                self._restore_dirs(old)


class RouterPoolRoutingTests(unittest.TestCase):
    def test_pool_round_robins(self):
        router._POOL_CURSORS.pop("frontend", None)
        try:
            first, _ = router.route_payload({
                "task_id": "p1", "type": "frontend", "prompt": "x", "workspace_path": "/tmp/p",
            })
            second, _ = router.route_payload({
                "task_id": "p2", "type": "frontend", "prompt": "x", "workspace_path": "/tmp/p",
            })
            third, _ = router.route_payload({
                "task_id": "p3", "type": "frontend", "prompt": "x", "workspace_path": "/tmp/p",
            })
            self.assertEqual([first, second, third], ["branch_pixel", "branch_brendan", "branch_pixel"])
        finally:
            router._POOL_CURSORS.pop("frontend", None)

    def test_senior_only_types_skip_pool(self):
        for solo_type, expected in [("spec_review", "branch_linus"), ("decompose", "branch_linus"), ("report", "branch_ada")]:
            branch_id, _ = router.route_payload({
                "task_id": f"t-{solo_type}", "type": solo_type, "prompt": "x", "workspace_path": "/tmp/p",
            })
            self.assertEqual(branch_id, expected)

    def test_new_task_types_route_to_correct_persona(self):
        cases = [
            ("spec_review", "Linus"),
            ("decompose", "Linus"),
            ("wireframe", "Pixel"),
            ("portfolio_query", "Linus"),
            ("portfolio_contribute", "Grace"),
            ("uat", "Kent"),
            ("report", "Ada"),
        ]
        for task_type, expected_agent in cases:
            with self.subTest(task_type=task_type):
                _, payload = router.route_payload({
                    "task_id": f"t-{task_type}",
                    "type": task_type,
                    "prompt": "x",
                    "workspace_path": "/tmp/p",
                })
                self.assertEqual(payload["agent"], expected_agent)


class IssueChannelTests(unittest.TestCase):
    """Contract tests for the issue-channel layer (worker helper + listener persistence)."""

    def _make_client(self):
        from unittest.mock import MagicMock
        return MagicMock()

    def test_publish_issue_validates_severity(self):
        # Bad severity must raise before any publish attempt.
        client = self._make_client()
        with self.assertRaises(ValueError):
            worker.publish_issue(
                client, "proj-1", "Linus", "task-1",
                "explode", "subject", "body", "cto",
            )
        client.publish.assert_not_called()

    def test_publish_issue_validates_requires(self):
        client = self._make_client()
        with self.assertRaises(ValueError):
            worker.publish_issue(
                client, "proj-1", "Linus", "task-1",
                "block", "subject", "body", "aliens",
            )
        client.publish.assert_not_called()

    def test_publish_issue_publishes_to_project_topic(self):
        client = self._make_client()
        worker.publish_issue(
            client, "proj-abc", "Linus", "task-99",
            "question", "What DB?", "Clarify schema.", "cto",
        )
        client.publish.assert_called_once()
        call_args = client.publish.call_args
        topic = call_args[0][0]
        self.assertEqual(topic, "agency/issues/proj-abc")
        self.assertEqual(call_args[1]["qos"], 1)

    def test_publish_issue_payload_shape(self):
        client = self._make_client()
        worker.publish_issue(
            client, "proj-xyz", "Ada", "task-42",
            "block", "Auth broken", "No token.", "ceo",
        )
        raw_payload = client.publish.call_args[0][1]
        payload = json.loads(raw_payload)
        required_keys = {"issue_id", "project_id", "from_agent", "task_id",
                         "severity", "subject", "body", "requires", "created_at"}
        for key in required_keys:
            self.assertIn(key, payload)
        self.assertTrue(payload["issue_id"].startswith("iss-"),
                        f"issue_id should start with 'iss-', got: {payload['issue_id']}")

    def test_listener_persists_issue_to_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_projects_dir = issue_listener.PROJECTS_DIR
            issue_listener.PROJECTS_DIR = root
            try:
                record = {
                    "issue_id": "iss-deadbeef",
                    "project_id": "proj-test",
                    "from_agent": "Linus",
                    "task_id": "task-1",
                    "severity": "info",
                    "subject": "FYI",
                    "body": "All good.",
                    "requires": "ceo",
                    "created_at": "2026-05-25T10:00:00+00:00",
                    "received_at": "2026-05-25T10:00:01+00:00",
                }
                issue_listener.persist_issue(record)

                issue_file = root / "proj-test" / "issues" / "iss-deadbeef.json"
                self.assertTrue(issue_file.exists(), "issue JSON file should be written")
                saved = json.loads(issue_file.read_text(encoding="utf-8"))
                self.assertEqual(saved["issue_id"], "iss-deadbeef")
                self.assertEqual(saved["project_id"], "proj-test")

                history_file = root / "proj-test" / "issues" / "_history.jsonl"
                self.assertTrue(history_file.exists(), "_history.jsonl should be appended")
                lines = history_file.read_text(encoding="utf-8").strip().splitlines()
                self.assertEqual(len(lines), 1)
                self.assertEqual(json.loads(lines[0])["issue_id"], "iss-deadbeef")
            finally:
                issue_listener.PROJECTS_DIR = old_projects_dir

    def test_listener_block_cto_flips_manifest_to_board_meeting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_projects_dir = issue_listener.PROJECTS_DIR
            issue_listener.PROJECTS_DIR = root
            try:
                project_dir = root / "proj-board"
                (project_dir / "issues").mkdir(parents=True, exist_ok=True)
                manifest = {
                    "project_id": "proj-board",
                    "name": "Board Test",
                    "stage": "spec",
                    "status": "stage_in_progress",
                    "open_action": "linus",
                    "stage_history": [],
                    "updated_at": "2026-05-25T10:00:00+00:00",
                }
                manifest_path = project_dir / "manifest.json"
                manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

                record = {
                    "issue_id": "iss-blocker1",
                    "project_id": "proj-board",
                    "from_agent": "Linus",
                    "task_id": "task-spec",
                    "severity": "block",
                    "subject": "Scope unclear",
                    "body": "Need CEO input.",
                    "requires": "cto",
                    "created_at": "2026-05-25T10:00:00+00:00",
                    "received_at": "2026-05-25T10:00:01+00:00",
                }
                issue_listener.persist_issue(record)

                updated = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual(updated["status"], "board_meeting")
                self.assertEqual(updated["open_action"], "ceo")
                # Original fields preserved.
                self.assertEqual(updated["stage"], "spec")
                self.assertEqual(updated["project_id"], "proj-board")
                # History entry appended.
                self.assertTrue(any(
                    "iss-blocker1" in (h.get("note") or "")
                    for h in updated["stage_history"]
                ))
            finally:
                issue_listener.PROJECTS_DIR = old_projects_dir

    def test_listener_rejects_path_traversal_project_id(self):
        # "../../../etc" sanitises to "etc" — no actual traversal outside root.
        # Verify the file lands under root/etc/..., NOT outside root.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_projects_dir = issue_listener.PROJECTS_DIR
            issue_listener.PROJECTS_DIR = root
            try:
                record = {
                    "issue_id": "iss-safe",
                    "project_id": "../../../etc",
                    "from_agent": "Linus",
                    "task_id": "task-1",
                    "severity": "info",
                    "subject": "test",
                    "body": "test",
                    "requires": "ceo",
                    "created_at": "2026-05-25T10:00:00+00:00",
                }
                issue_listener.persist_issue(record)
                # Traversal chars stripped -> sanitised id is "etc".
                # File must land inside root, not at a real /etc.
                sanitised_dir = root / "etc" / "issues"
                self.assertTrue(sanitised_dir.exists(), "sanitised dir should exist inside root")
                # Real /etc must not have been touched.
                real_etc_issue = Path("/etc/issues/iss-safe.json")
                self.assertFalse(real_etc_issue.exists(), "must not write to real /etc")
            finally:
                issue_listener.PROJECTS_DIR = old_projects_dir


if __name__ == "__main__":
    unittest.main()
