#!/usr/bin/env python3
"""CPU-default scalar TopK diagnostic; optional bounded gfx803 replay.
No large tensors, no complex unary tests, no automatic retries.
"""
import argparse
import json
import traceback
import torch

def probe(device,dim,largest,ordered):
    stage="construct"
    try:
        x=torch.tensor(2.5,device=device,dtype=torch.float32,requires_grad=True)
        stage="topk"
        v,i=torch.topk(x,1,dim=dim,largest=largest,sorted=ordered)
        if device!="cpu": torch.cuda.synchronize()
        stage="semantic"
        assert v.ndim==i.ndim==0 and i.dtype==torch.int64
        assert v.item()==2.5 and i.item()==0
        stage="backward"
        v.backward()
        if device!="cpu": torch.cuda.synchronize()
        assert x.grad.ndim==0 and x.grad.item()==1
        return dict(status="pass")
    except Exception:
        return dict(status="fail",stage=stage,traceback=traceback.format_exc())

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--gpu",action="store_true")
    p.add_argument("--dim",type=int,choices=[-1,0],default=-1)
    p.add_argument("--smallest",action="store_true")
    p.add_argument("--unsorted",action="store_true")
    a=p.parse_args()
    device="cpu"
    if a.gpu:
        if not torch.version.hip or not torch.cuda.is_available():
            p.error("HIP GPU required")
        props=torch.cuda.get_device_properties(0)
        if getattr(props,"gcnArchName","").split(":")[0]!="gfx803":
            p.error("gfx803 required")
        device="cuda:0"
    result=probe(device,a.dim,not a.smallest,not a.unsorted)
    print(json.dumps(dict(device=device,torch=torch.__version__,hip=torch.version.hip,
                          dim=a.dim,largest=not a.smallest,sorted=not a.unsorted,**result)))
    return 0 if result["status"]=="pass" else 1
if __name__=="__main__":
    raise SystemExit(main())
