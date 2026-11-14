/* CPU-only C1b GFX8 recovery behavioural fault-injection model.
 * This is NOT an imported Linux driver, kernel patch or hardware acceptance.
 * cc -std=c11 -Wall -Wextra -Werror -pedantic -O2 -o /tmp/c1b scripts/gfx803_kfd_c1b_mock.c
 * /tmp/c1b
 */
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

enum stage { PACKET_MGR, SCHED_RESOURCES, GTT_FENCE, DETECT_HANG, EXEC_QUEUES };
enum { NNODES = 3, NEG_EIO = -5, NEG_ENOMEM = -12 };

struct node {
    int start_error;
    enum stage failed_stage;
    int exec_error;
    bool sched_running;
    unsigned start_calls;
    unsigned exec_calls;
};
struct state {
    struct node nodes[NNODES];
    unsigned count, kfd_locked, reset_locks, reset_unlocks;
    unsigned scheduler_starts, scheduler_stops, failure_markers;
    unsigned resume_order, scheduler_order, ordinal;
    int post_reset_error;
};

/* Model of four explicit start_cpsch errors versus the unchecked
 * execute_queues_cpsch result. No GPU or kernel code executes. */
static int dqm_start_model(struct node *n)
{
    n->start_calls++;
    if (n->start_error) return n->start_error;
    n->sched_running = true;
    n->exec_calls++;
    /* Original code ignores the n->exec_error equivalent. */
    return 0;
}

/* Mimics the legacy kgd2kfd_post_reset early-return branch. */
static int kfd_post_reset_legacy(struct state *s)
{
    unsigned i;
    for (i = 0; i < s->count; ++i) {
        int ret = dqm_start_model(&s->nodes[i]);
        if (ret) return ret;
    }
    assert(s->kfd_locked);
    --s->kfd_locked;
    return 0;
}

/* Candidate contract only: retain KFD lock on failed startup,
 * propagate error and mark it. Releasing the lock could be unsafe. */
static int kfd_post_reset_checked(struct state *s)
{
    unsigned i;
    for (i = 0; i < s->count; ++i) {
        int ret = dqm_start_model(&s->nodes[i]);
        if (ret) { ++s->failure_markers; return ret; }
    }
    assert(s->kfd_locked);
    --s->kfd_locked;
    return 0;
}

static int gpu_recover_legacy(struct state *s)
{
    ++s->reset_locks;
    ++s->scheduler_starts;
    s->scheduler_order = ++s->ordinal;
    s->resume_order = ++s->ordinal;
    (void) kfd_post_reset_legacy(s); /* dropped return */
    ++s->reset_unlocks;
    return 0;
}

/* Proposed *semantic* contract, not proposed Linux C change:
 * post-reset before scheduler; report error; always unlock reset. */
static int gpu_recover_checked(struct state *s)
{
    int ret;
    ++s->reset_locks;
    s->resume_order = ++s->ordinal;
    ret = kfd_post_reset_checked(s);
    if (ret) {
        s->post_reset_error = ret;
        goto unlock;
    }
    ++s->scheduler_starts;
    s->scheduler_order = ++s->ordinal;
unlock:
    ++s->reset_unlocks;
    return ret;
}

static struct state initial(unsigned count)
{
    struct state s;
    memset(&s, 0, sizeof(s));
    assert(count && count <= NNODES);
    s.count = count;
    s.kfd_locked = 1;
    s.scheduler_stops = 1;
    return s;
}

static void test_legacy_silent_failure(void)
{
    struct state s = initial(2);
    s.nodes[0].start_error = NEG_EIO;
    assert(gpu_recover_legacy(&s) == 0);
    assert(s.kfd_locked == 1 && s.scheduler_starts == 1);
    assert(s.scheduler_order < s.resume_order);
    assert(s.nodes[1].start_calls == 0);
    assert(s.reset_locks == s.reset_unlocks);
}

static void test_success(void)
{
    struct state s = initial(3);
    unsigned i;
    assert(gpu_recover_checked(&s) == 0);
    assert(s.kfd_locked == 0 && s.failure_markers == 0);
    assert(s.scheduler_starts == s.scheduler_stops);
    assert(s.resume_order < s.scheduler_order);
    for (i = 0; i < s.count; ++i)
        assert(s.nodes[i].sched_running && s.nodes[i].start_calls == 1);
    assert(s.reset_locks == s.reset_unlocks);
}

static void test_first_node_error(void)
{
    struct state s = initial(2);
    s.nodes[0].start_error = NEG_ENOMEM;
    assert(gpu_recover_checked(&s) == NEG_ENOMEM);
    assert(s.post_reset_error == NEG_ENOMEM && s.failure_markers == 1);
    assert(s.kfd_locked == 1 && s.scheduler_starts == 0);
    assert(s.nodes[1].start_calls == 0);
    assert(s.reset_locks == s.reset_unlocks);
}

static void test_each_explicit_start_failure(void)
{
    enum stage at;
    for (at = PACKET_MGR; at <= DETECT_HANG; ++at) {
        struct state s = initial(1);
        s.nodes[0].failed_stage = at;
        s.nodes[0].start_error = NEG_ENOMEM;
        assert(gpu_recover_checked(&s) == NEG_ENOMEM);
        assert(s.post_reset_error == NEG_ENOMEM);
        assert(s.kfd_locked == 1 && s.scheduler_starts == 0);
        assert(s.reset_locks == s.reset_unlocks);
    }
}

static void test_partial_multinode_start(void)
{
    struct state s = initial(3);
    s.nodes[1].start_error = NEG_EIO;
    assert(gpu_recover_checked(&s) == NEG_EIO);
    assert(s.nodes[0].sched_running && !s.nodes[1].sched_running);
    assert(s.nodes[2].start_calls == 0 && s.scheduler_starts == 0);
    assert(s.kfd_locked == 1);
    assert(s.reset_locks == s.reset_unlocks);
    /* Partial start needs actual kernel cleanup review. */
}

static void test_unchecked_queue_mapping_error(void)
{
    struct state s = initial(1);
    s.nodes[0].exec_error = NEG_EIO;
    assert(gpu_recover_checked(&s) == 0);
    assert(s.nodes[0].sched_running && s.nodes[0].exec_calls == 1);
    assert(s.failure_markers == 0);
    /* An unpropagated execute_queues error bypasses outer correction. */
}

static void test_failed_recovery_stays_stopped(void)
{
    struct state s = initial(1);
    s.nodes[0].start_error = NEG_EIO;
    assert(gpu_recover_checked(&s) == NEG_EIO);
    assert(s.scheduler_starts == 0 && s.scheduler_stops == 1);
    assert(s.reset_locks == s.reset_unlocks);
}

int main(void)
{
    test_legacy_silent_failure();
    test_success();
    test_first_node_error();
    test_each_explicit_start_failure();
    test_partial_multinode_start();
    test_unchecked_queue_mapping_error();
    test_failed_recovery_stays_stopped();
    puts("C1b behavioral model: 7/7 PASS (CPU only; kernel/hardware unqualified)");
    return 0;
}
