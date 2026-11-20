"""Bounded residual-head reduction and AdamW differential diagnostic.

Source geometry: LeechTransformer 116e36df, models/x369_shared_head.py
and models/trialectic_wave_prior.py. Synthetic fixed cotangents; no routing
or model training. No large TopK, no CPU fallback for GPU mode.
"""
import argparse
import hashlib
import json
import math
import torch
import torch.nn.functional as F


def digest(t):
    return hashlib.sha256(t.detach().cpu().contiguous().numpy().tobytes()).hexdigest()


def scores(x, h, w, fused):
    # x is already cyclically rotated. Compare directed half only.
    a,b,c=x.reshape(x.shape[0],-1,3).unbind(-1)
    if fused:
        s,f,r=w.reshape(-1,3).unbind(-1)
        z=torch.stack((s*a+r*b+f*c,f*a+s*b+r*c,r*a+f*b+s*c),-1).reshape_as(x)
        return torch.bmm(h,z.unsqueeze(-1)).squeeze(-1)
    A,B,C=h.reshape(*h.shape[:-1],-1,3).unbind(-1)
    a,b,c=(v[:,None,:] for v in (a,b,c))
    features=torch.stack((a*A+b*B+c*C,a*B+b*C+c*A,a*C+b*A+c*B),-1).reshape_as(h)
    return F.linear(features,w).squeeze(-1)


def gradient(x,h,w,q,device,dtype,fused):
    x,h,w,q=[v.to(device=device,dtype=dtype) for v in (x,h,w,q)]
    w=w.detach().requires_grad_()
    y=scores(x,h,w,fused)
    g,=torch.autograd.grad(y,w,q)
    if not torch.isfinite(g).all() or not torch.isfinite(y).all():
        raise RuntimeError("nonfinite score or gradient")
    return g.detach().cpu()


def metrics(a,b):
    a,b=a.double(),b.double()
    d=(a-b).abs()
    if not torch.isfinite(d).all():
        raise RuntimeError("nonfinite difference")
    i=int(d.argmax())
    return dict(max_abs=float(d.max()),index=i,left=float(a.flatten()[i]),
                right=float(b.flatten()[i]),equal=bool(torch.equal(a,b)))


def adam(w, grads, device, foreach):
    p=torch.nn.Parameter(w.to(device).clone())
    opt=torch.optim.AdamW([p],lr=1e-4,eps=1e-8,foreach=foreach,fused=False)
    records=[]
    for g in grads:
        p.grad=g.to(device).clone()
        opt.step()
        state=opt.state[p]
        vals=[p.detach(),state["exp_avg"],state["exp_avg_sq"]]
        if any(not torch.isfinite(v).all() for v in vals):
            raise RuntimeError("nonfinite AdamW state")
        records.append([v.cpu().clone() for v in vals])
    return records


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cpu-only",action="store_true")
    p.add_argument("--device",default="cuda:0")
    a=p.parse_args()
    devices=["cpu"]
    receipt=dict(torch=torch.__version__,hip=torch.version.hip,
                 mode="CPU_ONLY" if a.cpu_only else "GFX803",cases=[])
    if not a.cpu_only:
        if not torch.version.hip or not torch.cuda.is_available():
            p.error("HIP gfx803 required; no fallback")
        dev=torch.device(a.device)
        if dev.type!="cuda":
            p.error("CUDA API device required")
        props=torch.cuda.get_device_properties(dev)
        if getattr(props,"gcnArchName","").split(":")[0]!="gfx803":
            p.error("gfx803 required")
        devices.append(str(dev))
        receipt.update(gpu=props.name,arch=props.gcnArchName)
    rng=torch.Generator().manual_seed(42)
    for scale in (1.,1e-4,1e-8):
        x=torch.randn(3,384,generator=rng)
        h=torch.randn(3,4,384,generator=rng)
        w=torch.randn(1,384,generator=rng)*.003
        q=torch.randn(3,4,generator=rng)*scale
        case=dict(scale=scale,input_hashes=[digest(v) for v in (x,h,w,q)],reductions={})
        ref=gradient(x,h,w,q,"cpu",torch.float64,False)
        for dev in devices:
            for dtype in (torch.float32,torch.float64):
                g=[gradient(x,h,w,q,dev,dtype,f) for f in (False,True)]
                case["reductions"][dev+":"+str(dtype)]=dict(
                    pair=metrics(*g),reference=[metrics(v,ref) for v in g],
                    hashes=[digest(v) for v in g])
        # Freeze the exact CPU FP32 gradient bytes; separate optimizer from reductions.
        g=gradient(x,h,w,q,"cpu",torch.float32,False)
        # Include near-zero coordinates and sign reversals without changing input bytes
        # across devices. Fixed sequence is not recurrent model training.
        g=g.clone()
        g[0,:5]=torch.tensor([0.,1e-8,-1e-8,1e-12,-1e-12])
        grads=[g if i%2==0 else -g for i in range(20)]
        case["optimizer_gradient_hashes"]=[digest(v) for v in grads]
        case["optimizer"]={}
        for foreach in (False,True):
            cpu=adam(w,grads,"cpu",foreach)
            for dev in devices:
                out=adam(w,grads,dev,foreach)
                repeat=adam(w,grads,dev,foreach)
                case["optimizer"][str(foreach)+":"+dev]=dict(
                    steps=[dict(step=i+1,cpu_reference=[metrics(u,v) for u,v in zip(row,cpu[i])],
                                repeat=[metrics(u,v) for u,v in zip(row,repeat[i])])
                           for i,row in enumerate(out)])
        receipt["cases"].append(case)
    receipt["status"]="MEASURED_NOT_CERTIFIED"
    print(json.dumps(receipt,indent=2,allow_nan=False))


if __name__=="__main__":
    main()
