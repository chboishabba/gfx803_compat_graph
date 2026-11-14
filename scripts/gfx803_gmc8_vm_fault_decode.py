#!/usr/bin/env python3
"""Decode retained GFX8 VM fault status registers without GPU access.

Values are taken from Linux v7.3's gmc_8_1_sh_mask.h, and the human-readable
log interpretation from gmc_v8_0_vm_decode_fault. The PROTECTIONS field is a
bitset, not an enum identifying a unique PTE failure cause.
"""
from __future__ import annotations

import argparse
import json

PROTECTIONS_MASK = 0xff
VMID_MASK = 0x1e000000
VMID_SHIFT = 25
CLIENT_ID_MASK = 0x1ff000
CLIENT_ID_SHIFT = 12
READ_WRITE_MASK = 0x1000000


def decode(status: int, client: int | None = None) -> dict:
    if status < 0 or status > 0xffffffff:
        raise ValueError("expected 32-bit unsigned VM_CONTEXT1_PROTECTION_FAULT_STATUS")
    result = {
        "status_hex": f"0x{status:08x}",
        "vmid": (status & VMID_MASK) >> VMID_SHIFT,
        "protections_bits": status & PROTECTIONS_MASK,
        "protections_hex": f"0x{status & PROTECTIONS_MASK:02x}",
        "memory_client_id": (status & CLIENT_ID_MASK) >> CLIENT_ID_SHIFT,
        "access": "write" if status & READ_WRITE_MASK else "read",
        "unique_pte_cause_inferable": False,
    }
    if client is not None:
        if client < 0 or client > 0xffffffff:
            raise ValueError("expected 32-bit unsigned memory client register")
        result["memory_client_register_hex"] = f"0x{client:08x}"
        result["memory_client_ascii"] = "".join(
            chr((client >> shift) & 0xff) if 32 <= (client >> shift) & 0xff < 127 else "."
            for shift in (24, 16, 8, 0)
        )
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--status", type=lambda x: int(x, 0), required=True)
    p.add_argument("--client", type=lambda x: int(x, 0))
    args = p.parse_args()
    print(json.dumps(decode(args.status, args.client), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
