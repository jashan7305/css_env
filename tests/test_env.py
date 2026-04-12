import json

from fastapi.testclient import TestClient

from server.app import app
from server.css_env_environment import CssEnvironment
from server.tasks import TASKS


def test_task_configs_expose_grader_weights() -> None:
    for task_name in ("task1", "task2", "task3"):
        task = TASKS[task_name]
        weights = task.get("grader_weights")

        assert isinstance(weights, dict)
        assert weights
        assert all(isinstance(v, (int, float)) for v in weights.values())


class TestGraders:
    def test_tasks_json_has_at_least_three_enabled_task_graders(self) -> None:
        with open("tasks.json", "r", encoding="utf-8") as f:
            payload = json.load(f)

        tasks = payload.get("tasks", [])
        enabled = [
            task
            for task in tasks
            if task.get("enabled", True) and task.get("grader_id") and task.get("task_id")
        ]
        assert len(enabled) >= 3

    def test_task_scores_are_strictly_between_zero_and_one(self) -> None:
        env = CssEnvironment()

        for task_name in ("task1", "task2", "task3", "task4"):
            task = TASKS[task_name]
            env.reset(task=task, seed=7)
            result = env.grade()
            assert 0.0 < float(result.score) < 1.0

    def test_grade_uses_only_non_zero_weight_dimensions(self) -> None:
        env = CssEnvironment()
        task = dict(TASKS["task1"])
        task["grader_weights"] = {"color": 0.7, "spacing": 0.3, "typography": 0.0}
        task["graders"] = ["color", "spacing", "typography"]

        env.reset(task=task, seed=3)
        result = env.grade()

        assert set(result.breakdown.keys()) == {"color", "spacing"}
        assert set(result.details.keys()) == {"color", "spacing"}
        assert 0.0 < float(result.score) < 1.0

    def test_grade_endpoint_returns_grade_result_payload(self) -> None:
        client = TestClient(app)

        reset_response = client.post("/reset", json={"task_name": "task1", "seed": 5})
        assert reset_response.status_code == 200

        grade_response = client.get("/grade")
        assert grade_response.status_code == 200

        payload = grade_response.json()
        assert "score" in payload
        assert "breakdown" in payload
        assert "details" in payload
        assert isinstance(payload["breakdown"], dict)
        assert isinstance(payload["details"], dict)
        assert 0.0 < float(payload["score"]) < 1.0
