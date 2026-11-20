import unittest
from fractions import Fraction
import torch
from scripts.gfx803_fp32_adamw_differential import exact_gradient, exact_metrics, gradient, adam, metrics

class ExactReduction(unittest.TestCase):
    def test_orientation(self):
        x=torch.tensor([[1.,2.,3.]])
        h=torch.tensor([[[4.,5.,6.]]])
        q=torch.tensor([[2.]])
        ref=exact_gradient(x,h,q)
        self.assertEqual(ref,[Fraction(64),Fraction(58),Fraction(58)])
        for fused in (False,True):
            g=gradient(x,h,torch.ones(1,3),q,"cpu",torch.float64,fused)
            self.assertEqual(exact_metrics(g,ref)["exact_error"],"0")

    def test_asymmetric_orientation(self):
        x=torch.tensor([[1.,0.,0.]])
        h=torch.tensor([[[2.,3.,5.]]])
        q=torch.ones(1,1)
        ref=exact_gradient(x,h,q)
        self.assertEqual(ref,[2,3,5])
        for fused in (False,True):
            g=gradient(x,h,torch.ones(1,3),q,"cpu",torch.float64,fused)
            self.assertEqual(exact_metrics(g,ref)["max_abs"],0)

    def test_near_zero_repeat(self):
        w=torch.zeros(1,3)
        g=torch.tensor([[0.,1e-8,-1e-8]])
        a=adam(w,[g,-g],"cpu",False)
        b=adam(w,[g,-g],"cpu",False)
        self.assertTrue(all(metrics(u,v)["equal"] for x,y in zip(a,b) for u,v in zip(x,y)))
