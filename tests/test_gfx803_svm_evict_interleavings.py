"""CPU-only exhaustive two-invalidator model of Linux v7.3 kfd_svm.c.

Model assumes the first quiesce succeeds. It proves a possible notification
ordering, NOT that the historical RX 580 hang used this SVM path.
"""
from collections import deque
import unittest


def explore(serialized, quiesce_succeeds=True):
    """Enumerate all interleavings of two concurrent distinct-range invalidations.

    Each actor:
      0 enters notifier, 1 takes process eviction lock (if available),
      2 increments evicted_ranges, 3 completes first quiesce (if first),
      4 returns from notifier, 5 done.
    """
    initial = ((0, 0), -1, 0, False, ())
    todo = deque([initial])
    seen = set()
    unsafe = None
    terminal = 0
    while todo:
        pcs, owner, evicted, stopped, trace = todo.popleft()
        state = (pcs, owner, evicted, stopped)
        if state in seen:
            continue
        seen.add(state)
        if pcs == (5, 5):
            terminal += 1
            continue
        for actor in (0, 1):
            pc = pcs[actor]
            if pc == 5:
                continue
            new_pcs = list(pcs)
            next_owner, next_evicted, next_stopped = owner, evicted, stopped
            label = None
            if pc == 0:
                new_pcs[actor] = 1
                label = "enter"
            elif pc == 1:
                if serialized and owner != -1:
                    continue
                next_owner = actor if serialized else -1
                new_pcs[actor] = 2
                label = "lock" if serialized else "no_lock"
            elif pc == 2:
                next_evicted += 1
                new_pcs[actor] = 3 if next_evicted == 1 else 4
                label = "first:begin_quiesce" if next_evicted == 1 else "later:skip_quiesce"
            elif pc == 3:
                next_stopped = quiesce_succeeds
                new_pcs[actor] = 4
                label = "first:quiesce_done" if next_stopped else "first:quiesce_failed"
            elif pc == 4:
                new_pcs[actor] = 5
                if serialized:
                    assert owner == actor
                    next_owner = -1
                label = "return_notifier"
                if not next_stopped and unsafe is None:
                    unsafe = (*trace, (actor, label))
            if label is not None:
                new_trace = (*trace, (actor, label))
                todo.append((tuple(new_pcs), next_owner, next_evicted,
                             next_stopped, new_trace))
    return {"states": len(seen), "terminal_states": terminal,
            "unsafe_trace": unsafe, "unsafe_possible": unsafe is not None}


class SvmEvictionInterleavingTests(unittest.TestCase):
    def test_v73_first_only_atomic_gate_allows_second_to_return_early(self):
        r = explore(serialized=False)
        self.assertTrue(r["unsafe_possible"])
        self.assertIn((1, "later:skip_quiesce"), r["unsafe_trace"])
        self.assertEqual(r["unsafe_trace"][-1][1], "return_notifier")

    def test_amd_reviewed_evict_lock_serializes_notifier_returns(self):
        r = explore(serialized=True)
        self.assertFalse(r["unsafe_possible"])
        self.assertGreater(r["states"], 0)
        self.assertGreater(r["terminal_states"], 0)

    def test_lock_does_not_turn_quiesce_failure_into_success(self):
        # A nonresponsive MEC/CP remains unsafe after a failed quiesce;
        # the lock fixes concurrent return ordering only.
        self.assertTrue(explore(serialized=True, quiesce_succeeds=False)["unsafe_possible"])

    def test_rfc_patch_contains_lock_lifecycle(self):
        from pathlib import Path
        p = (Path(__file__).resolve().parents[1] / "patches/linux" /
             "gfx803-t1-svm-concurrent-eviction-v73-rfc.patch")
        data = p.read_text()
        for term in ("+\tmutex_lock(&svms->evict_lock);",
                     "+\t\tmutex_unlock(&svms->evict_lock);",
                     "+\tmutex_init(&svms->evict_lock);",
                     "+\tmutex_destroy(&p->svms.evict_lock);"):
            if "mutex_lock" in term:  # Lock is nested inside the eviction branch.
                self.assertIn("+\t\tmutex_lock(&svms->evict_lock);", data)
            else:
                self.assertIn(term, data)


if __name__ == "__main__":
    unittest.main()
