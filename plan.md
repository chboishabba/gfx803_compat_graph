# Plan

## Milestone 1

- Make the framework rebuild driver use only the extracted old-ABI SDK/runtime roots.
- Reject any `/opt/rocm` leakage in the old-ABI smoke path.

## Milestone 2

- Rerun the torch smoke on the preserved old-ABI lane.
- Confirm whether the rebuilt wheel can import and see the GPU.

## Milestone 3

- If torch smoke passes, continue to `torchvision` and `torchaudio`.
- If torch smoke fails, repair the runtime boundary before proceeding.
