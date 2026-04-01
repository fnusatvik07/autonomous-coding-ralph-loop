"""Tests for parallel task execution (unit tests, no git worktrees required)."""

from ralph.parallel import find_independent_tasks
from ralph.models import PRD, Task, TaskStatus


class TestFindIndependentTasks:
    def test_no_tasks(self):
        prd = PRD(project_name="test", tasks=[])
        assert find_independent_tasks(prd) == []

    def test_all_same_priority(self):
        prd = PRD(project_name="test", tasks=[
            Task(id="T-1", title="A", description="d", priority=1),
            Task(id="T-2", title="B", description="d", priority=1),
            Task(id="T-3", title="C", description="d", priority=1),
        ])
        batches = find_independent_tasks(prd)
        assert len(batches) == 1
        assert len(batches[0]) == 3

    def test_sequential_priorities(self):
        prd = PRD(project_name="test", tasks=[
            Task(id="T-1", title="A", description="d", priority=1),
            Task(id="T-2", title="B", description="d", priority=2),
            Task(id="T-3", title="C", description="d", priority=3),
        ])
        batches = find_independent_tasks(prd)
        assert len(batches) == 3
        assert all(len(b) == 1 for b in batches)

    def test_mixed_priorities(self):
        prd = PRD(project_name="test", tasks=[
            Task(id="T-1", title="A", description="d", priority=1),
            Task(id="T-2", title="B", description="d", priority=2),
            Task(id="T-3", title="C", description="d", priority=2),
            Task(id="T-4", title="D", description="d", priority=3),
        ])
        batches = find_independent_tasks(prd)
        assert len(batches) == 3
        assert len(batches[0]) == 1  # priority 1
        assert len(batches[1]) == 2  # priority 2 (parallel)
        assert len(batches[2]) == 1  # priority 3

    def test_max_parallel_cap(self):
        prd = PRD(project_name="test", tasks=[
            Task(id=f"T-{i}", title=f"Task {i}", description="d", priority=1)
            for i in range(10)
        ])
        batches = find_independent_tasks(prd, max_parallel=3)
        assert len(batches[0]) == 3  # Capped at 3

    def test_skips_completed_tasks(self):
        prd = PRD(project_name="test", tasks=[
            Task(id="T-1", title="Done", description="d", priority=1, status=TaskStatus.PASSED),
            Task(id="T-2", title="Pending", description="d", priority=2),
        ])
        batches = find_independent_tasks(prd)
        assert len(batches) == 1
        assert batches[0][0].id == "T-2"
