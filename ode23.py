#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan  6 19:29:35 2019

@author: mschafer
"""
import math
from functools import partial

# https://blogs.mathworks.com/cleve/2014/05/26/ordinary-differential-equation-solvers-ode23-and-ode45/
def ode23(f, x0):
    h = .1
    x = x0
    t = 0
    
    # first stage
    s1 = f(t, x)
    
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
        x[idx] = h / 9. * (2.*s1[idx] + 3*s2[idx] + 4*s3[idx])
    
    # s4 is same as s1 for next step    
    s4 = f(t, x)

    # error: h*(-5*s1 + 6*s2 + 8*s3 + -9*s4)/72
    e = x
    for idx in range(len(x)):
        e[idx] = h / 72. * (-5.*s1[idx] + 6*s2[idx] + 8*s3[idx] - 9.*s4[idx])
    return e
    

def rhs(t, x):
    return [-math.sin(t), math.cos(t)]

class Circle:
    def __init__(self, radius):
        self.radius = radius
        
    def rhs(self, t, x):
        return [-math.sin(t)*self.radius, math.cos(t)*self.radius]

if __name__ == "__main__":
    print ("hello world")
    circ = Circle(4)
    # f= rhs
    f = partial(Circle.rhs, circ)
    e = ode23(f, [1, 0])
    print ("error " + repr(e))
    