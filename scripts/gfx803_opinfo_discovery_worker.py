#!/usr/bin/env python3
"""Run ordered pytest nodes in one process, journalling start/result events."""
import argparse, json, os, sys, time
from pathlib import Path

def emit(path, event, nodeid, **extra):
    row={"event":event,"nodeid":nodeid,"unix":time.time(),**extra}
    with path.open("a") as f:
        f.write(json.dumps(row,sort_keys=True)+"\n"); f.flush(); os.fsync(f.fileno())

class Journal:
    def __init__(self,path): self.path=path
    def pytest_runtest_logstart(self,nodeid,location): emit(self.path,"start",nodeid)
    def pytest_runtest_logreport(self,report):
        if report.when=="call": emit(self.path,"result",report.nodeid,outcome=report.outcome)
        elif report.when=="setup" and report.skipped: emit(self.path,"result",report.nodeid,outcome="skipped")

def main():
    p=argparse.ArgumentParser(); p.add_argument("--journal",type=Path,required=True); p.add_argument("nodes",nargs="+"); a=p.parse_args()
    import pytest
    raise SystemExit(pytest.main(["-q",*a.nodes],plugins=[Journal(a.journal)]))
if __name__=="__main__": main()
