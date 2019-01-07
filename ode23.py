#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan  6 19:29:35 2019

@author: mschafer
"""
import math

# https://blogs.mathworks.com/cleve/2014/05/26/ordinary-differential-equation-solvers-ode23-and-ode45/
def ode23(f, x0):
    h = .1
    x = x0
    t = 0
    s1 = f(t, x)
    
    xs1 = [h/2 * z for z in s1]
    x1 = [a+b for a,b in zip(x,xs1)]
    s2 = f(t+h/2, x1)
    
    
    s3 = f(t+3*h/4, x + 3*h*s2/4)
    x = x + h*(2*s1 + 3*s2 + 4*s3)/9
    t = t + h
    s4 = f(t, x)
    e = h*(-5*s1 + 6*s2 + 8*s3 + -9*s4)/72
    return e
    

def rhs(t, x):
    return [-math.sin(t), math.cos(t)]

if __name__ == "__main__":
    print ("hello world")
    f = rhs
    e = ode23(f, [1, 0])
    print ("error " + repr(e))
    