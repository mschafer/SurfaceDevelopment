#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan  6 19:29:35 2019

@author: mschafer
"""
import math
from functools import partial

absTol = None
relTol = 1.e-4
defaultAbsTol = 1.e-6

# estimate intial step size
# 1 / max (dx/dt / x0_threshold)
def estimateH(f, x0, t0):
    f0 = f(t0, x0)
    rh = 0.
    for i in range(len(x0)):
        atol = defaultAbsTol
        if absTol != None:
            atol = absTol[i]

        x = max(atol/relTol, abs(x0[i]))
        rh = max(abs(f0[i]) / x, rh)

    return 1. / rh


# https://blogs.mathworks.com/cleve/2014/05/26/ordinary-differential-equation-solvers-ode23-and-ode45/
def ode23(f, x0, tvec):
    x = x0[:]
    t = tvec[0]
    
    xOut = []
    xOut.append(x0[:])
    eOut = []
    
    s1 = f(t, x)
    for it in range(1, len(tvec)):
        h = tvec[it] - tvec[it-1]
    
        #stage 2: s2 = f(t+h/2, x + 1/2 h s1)
        xs1 = [h/2. * z for z in s1]
        x1 = [a+b for a,b in zip(x,xs1)]
        s2 = f(t+h/2., x1)
    
        # stage 3: s3 = f(t+3h/4, x + 3/4 h s2)
        xs2 = [3.*h/4. * z for z in s2]
        x2 = [a+b for a,b in zip(x,xs2)]
        s3 = f(t+3.*h/4., x2)
    
        #output: t = t+h, x = x + h/9(2 s1 + 3 s2 + 4 s3)
        t = t + h
        for idx in range(len(x)):
            x[idx] = x[idx] + h / 9. * (2.*s1[idx] + 3*s2[idx] + 4*s3[idx])
    
        xOut.append(x[:])
        # s4 is same as s1 for next step    
        s4 = f(t, x)

        # error: h*(-5*s1 + 6*s2 + 8*s3 + -9*s4)/72
        # err = absh * norm(e ./ max(max(abs(y),abs(ynew)),threshold),inf);
        # fail if err > rtol            
        # threshold is atol / rtol
        threshold = [.01 for idx in range(len(x))]
        success = True
        e = [0 for idx in range(len(x))]
        for idx in range(len(x)):
            atol = defaultAbsTol
            if absTol != None:
                atol = absTol[idx]

            threshold = atol / relTol
            e[idx] = h / 72. * (-5.*s1[idx] + 6*s2[idx] + 8*s3[idx] - 9.*s4[idx])
            err = e[idx] / max(threshold, abs(x[idx]))
            if err > relTol:
                success = False


        eOut.append(e[:])
        # FSAL
        s1 = s4
        
    return xOut, success
        
def linspace(start, end, steps):
    ans = []
    d = (end-start) / (steps-1)
    for i in range(steps):
        v = (i * d) + start
        ans.append(v)
    ans[0] = start
    ans[-1] = end
    return ans


def rhs(t, x):
    return [-math.sin(t), math.cos(t)]

class Circle:
    def __init__(self, radius):
        self.radius = radius
        
    def rhs(self, t, x):
        return [-math.sin(t)*self.radius, math.cos(t)*self.radius]

if __name__ == "__main__":
    absTol = [1.e-5, 1.e-5]
    print ("hello world")
    circ = Circle(1)
    # f= rhs
    f = partial(Circle.rhs, circ)
    h0 = estimateH(f, [1., 0.], 0.)

    tvec = linspace(0., .4, 5)
    [x, success] = ode23(f, [1, 0], tvec)
    print (len(x))
    