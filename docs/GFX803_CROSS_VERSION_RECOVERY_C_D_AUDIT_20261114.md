# GFX8 cross-distro recovery — source-level C/D audit (2026-11-14)

**Scope:** upstream `torvalds/linux` tags v6.13, v6.19, v7.3; original RX 580/Polaris10 November journal; historical March Ollama/Wayland/WhisperX incident notes. **No GPU run, driver modification, backport acceptance, or module binary reproduction.** These are source results and incident chronology, not a demonstrated hardware root-cause fix.

## Outcome: source-level failure propagation is stronger than the reset-method guess

### C1 — KFD post-reset return is dropped across upstream tags

- `drivers/gpu/drm/amd/amdkfd/kfd_device.c::kgd2kfd_post_reset` loops over nodes, calls `kfd_resume(node)`, and returns its error immediately if the queue manager cannot start; the early return precedes `--kfd_locked`.
- `drivers/gpu/drm/amd/amdgpu/amdgpu_amdkfd.c::amdgpu_amdkfd_post_reset` *returns that status*.
- `drivers/gpu/drm/amd/amdgpu/amdgpu_device.c` calls the wrapper as a **discarded expression** in `amdgpu_device_gpu_resume` (v6.19/v7.3), and at the end of `amdgpu_device_gpu_recover` in v6.13. The outer GPU-recovery path does **not** merge the status into its result.
- The driver may print `GPU reset(n) succeeded!` **before** KFD post-reset runs. This means the printed success is not an end-to-end certificate that new compute queues work, much less that new Wayland clients can render.
- Source ancestry: [v6.13 AMDGPU device](https://github.com/torvalds/linux/blob/v6.13/drivers/gpu/drm/amd/amdgpu/amdgpu_device.c), [v6.19](https://github.com/torvalds/linux/blob/v6.19/drivers/gpu/drm/amd/amdgpu/amdgpu_device.c), [v7.3](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_device.c), [v7.3 KFD device](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdkfd/kfd_device.c) and [wrapper](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/amdgpu_amdkfd.c).

**Candidate correction:** first produce a *bounded, non-destructive* mocked kernel-source test for both `kfd_resume == 0` and `kfd_resume != 0`, and a reviewed patch that propagates or at minimum records the KFD error and marks recovery unqualified. Do **not** simply return before releasing reset locks, fail partially initialized node cleanup, or put DRM schedulers into an unbalanced stopped state. Error propagation is not the same as hardware reset repair.

**Critical nuance:** whether `kfd_resume` *actually failed* in any incident remains unknown. This code explains why an error could be hidden, not that it was.

### C2 — DRM scheduler restart happens before KFD callback in 6.13/6.19/7.3

- v7.3 `amdgpu_device_gpu_recover` calls `amdgpu_device_sched_resume` (around 5811) before `amdgpu_device_gpu_resume` (around 5815).
- `amdgpu_device_sched_resume` starts DRM scheduler work queues through `drm_sched_wqueue_start`; the later callback calls `amdgpu_amdkfd_post_reset`.
- This is a **source-visible admission window** for DRM scheduler jobs while KFD post-reset is unfinished. It is **not proof** that an existing KFD user process submitted a packet during this window. `kfd_locked` is held around reset, so saying KFD user-mode queue doorbells necessarily race here is too strong.
- Potential correction: move the KFD post-reset work before reopening DRM job submission with correct lock/error unwinding. The older AMD patch discussion proposed this ordering, but actual accepted review/merged status and Polaris regression testing are separate obligations.

### D1 — Actual Polaris reset route: BACO, not a guessed fallback

- v7.3 `vi.c::vi_asic_reset_method` on `CHIP_POLARIS10/11/12` selects `AMD_RESET_METHOD_BACO` if `amdgpu_dpm_is_baco_supported`; otherwise the legacy PCI-config reset path.
- `vi_asic_reset` prints `BACO reset` immediately before calling `amdgpu_dpm_baco_reset`, and prints `PCI CONFIG reset` for the alternate path.
- The **original November journal explicitly says `BACO reset`** at 12:39:29 and in later reset waves. This settles the reset method in that observed wave; no need to speculate about a PCI reset in its place.
- **Chronology:** November's initial KIQ ring-test `-110` is at 12:39:29 **before** the logged BACO call in the same wave. It therefore cannot be attributed *solely* to that BACO operation's *exit*. A preceding soft-reset sequence, an already-dead CP/KIQ, or a shared hardware nonprogress state remain candidates.
- Source: [v7.3 vi.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/vi.c); original [November journal](https://github.com/chboishabba/gfx803_compat_graph/blob/master/docs/receipts/gfx803_topk_pr8_review_safe_20261114/kernel-previous-boot.log).

### D2 — Exact GFX8 KIQ/KCQ ordering, not 'KIQ is the first tested ring'

- In `gfx_v8_0_cp_resume`, the code initializes KIQ, graphics CP, and compute queues; then `gfx_v8_0_cp_test_all_rings` tests **gfx first, KIQ second, compute afterward** (v7.3 around lines 4705–4752). A specific failed KIQ ring test says KIQ failed when tested, **not** that it was the first tested engine.
- `gfx_v8_0_kcq_disable` emits KIQ `PACKET3_UNMAP_QUEUES`, commits it, then calls `amdgpu_ring_test_helper(kiq_ring)`; nonzero result emits **`KCQ disable failed`** (around 4782–4816). This makes November's later KCQ error consistent with inability to execute queue-management packets on the KIQ path. It does not distinguish initial mechanism.
- Source: [v7.3 gfx_v8_0.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/gfx_v8_0.c).

### D3 — Polaris uses Tonga IH, not CIK IH

- `vi.c::vi_set_ip_blocks` explicitly adds `tonga_ih_ip_block` for `CHIP_POLARIS10/11/12` (around 2105–2113).
- `tonga_ih_disable_interrupts` clears enable bits and resets IH rptr/wptr to 0. `kfd_interrupt.c` maintains its own `ih_fifo` and `interrupts_active` flag; the reset path needs ordering analysis across that separate software FIFO and `kgd2kfd_interrupt`, not just the hardware IH pointers.
- In `kgd2kfd_interrupt`, `interrupts_active` guards enqueuing, but the existence of that guard **does not prove** KFD event-work items are drained or stale items are discarded on a GPU reset. Conversely a stale entry has **not been observed** in the historical incident logs.
- Relevant source: [v7.3 vi.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/vi.c), [tonga_ih.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdgpu/tonga_ih.c), [kfd_interrupt.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdkfd/kfd_interrupt.c), [kfd_device.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdkfd/kfd_device.c).

### D4 — Process teardown already has a reset-workqueue wait in v7.3

- `kfd_process.c::kfd_process_wq_release` calls `kfd_process_wait_gpu_reset_complete`; the latter `flush_workqueue(reset_domain->wq)`. Therefore a blanket claim that **no** wait exists for reset before process memory release is wrong.
- Later accepted MI300X v5 patch changes a *different timing/lifetime point*. Compare exact call sites and BO lifetime rather than assuming absence of all guards in Polaris.
- [v7.3 kfd_process.c](https://github.com/torvalds/linux/blob/v7.3/drivers/gpu/drm/amd/amdkfd/kfd_process.c).

## Minimal causal gates before editing a physical driver

| Gate | Targeted evidence / test | Outcome required |
| --- | --- | --- |
| C1a | Offline v6.13/v6.19/v7.3 exact source diff for `amdgpu_amdkfd_post_reset` return and `kgd2kfd_post_reset` early return | Source failure-propagation gap **CONFIRMED** |
| C1b | Mocked/no-GPU error injection for failed KFD queue start, locked-state cleanup and DRM scheduler admission | Test failure propagation without deadlocks/leaking reset locks |
| C2 | Kernel-version-specific AMD patch review and reverse-order callback with full cleanup | No premature graphics submission, no unsupported claim about KFD user process |
| D1 | BACO-vs-PCI mode from original logs plus firmware/reset-method source | **BACO** confirmed in November wave; first KIQ -110 preceded it |
| D2 | Source map KIQ/KCQ queue packet and test ordering | **Source-mapped**; no incident-time register/packet trace |
| D3 | Polaris Tonga IH software/hardware queue lifecycle across reset | IH IP assignment **CONFIRMED**; stale interrupt causal claim **OPEN** |
| D4 | KFD BO lifetime and accepted 2026 patch applicability | Generic release-work wait exists; specific MI300X UAF not proven on GFX8 |
| R | Independently recoverable GPU and post-fault GFX/KIQ/KCQ/KFD **plus a new Wayland context** | No hardware result yet |

**Disposition:** Direct attention next to KFD post-reset **error handling, process-lock state, and scheduler reopening**. Treat KIQ and BACO source sequencing as supporting discriminators. Do not apply AMD's NAK'd pre-reset-before-lock patch, or claim the accepted MI300X memory-free patch cures Polaris.
