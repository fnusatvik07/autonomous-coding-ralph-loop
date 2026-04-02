"""Tests for parallel feature execution."""

from ralph.parallel import find_independent_features
from ralph.models import PRD, Feature, Task, TaskStatus


class TestFindIndependentFeatures:
    def test_no_features(self):
        prd = PRD(project_name="test", features=[])
        assert find_independent_features(prd) == []

    def test_all_same_priority(self):
        prd = PRD(project_name="test", features=[
            Feature(id="F-1", title="A", priority=1, tasks=[Task(id="T-1", title="a")]),
            Feature(id="F-2", title="B", priority=1, tasks=[Task(id="T-2", title="b")]),
            Feature(id="F-3", title="C", priority=1, tasks=[Task(id="T-3", title="c")]),
        ])
        batches = find_independent_features(prd)
        assert len(batches) == 1
        assert len(batches[0]) == 3

    def test_sequential_priorities(self):
        prd = PRD(project_name="test", features=[
            Feature(id="F-1", title="A", priority=1, tasks=[Task(id="T-1", title="a")]),
            Feature(id="F-2", title="B", priority=2, tasks=[Task(id="T-2", title="b")]),
            Feature(id="F-3", title="C", priority=3, tasks=[Task(id="T-3", title="c")]),
        ])
        batches = find_independent_features(prd)
        assert len(batches) == 3
        assert all(len(b) == 1 for b in batches)

    def test_mixed_priorities(self):
        prd = PRD(project_name="test", features=[
            Feature(id="F-1", title="A", priority=1, tasks=[Task(id="T-1", title="a")]),
            Feature(id="F-2", title="B", priority=2, tasks=[Task(id="T-2", title="b")]),
            Feature(id="F-3", title="C", priority=2, tasks=[Task(id="T-3", title="c")]),
            Feature(id="F-4", title="D", priority=3, tasks=[Task(id="T-4", title="d")]),
        ])
        batches = find_independent_features(prd)
        assert len(batches) == 3
        assert len(batches[0]) == 1  # priority 1
        assert len(batches[1]) == 2  # priority 2 (parallel)
        assert len(batches[2]) == 1  # priority 3

    def test_max_parallel_cap(self):
        prd = PRD(project_name="test", features=[
            Feature(id=f"F-{i}", title=f"F{i}", priority=1, tasks=[Task(id=f"T-{i}", title=f"t{i}")])
            for i in range(10)
        ])
        batches = find_independent_features(prd, max_parallel=3)
        assert len(batches[0]) == 3

    def test_skips_completed_features(self):
        prd = PRD(project_name="test", features=[
            Feature(id="F-1", title="Done", priority=1, tasks=[
                Task(id="T-1", title="a", status=TaskStatus.PASSED),
            ]),
            Feature(id="F-2", title="Pending", priority=2, tasks=[
                Task(id="T-2", title="b"),
            ]),
        ])
        batches = find_independent_features(prd)
        assert len(batches) == 1
        assert batches[0][0].id == "F-2"
