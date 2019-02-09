import adsk.core, adsk.fusion, adsk.cam, traceback
import os, math
from .ode23 import ode23
from functools import partial

fitTolerance = .01 # cm database units

class FlatLoop:
    def __init__(self, loop):
        flatEdges = []
        for iedge in range(loop.coEdges.count):
            ce = loop.coEdges.item(iedge)
            fe = FlatEdge(ce.edge, loop.face)
            flatEdges.append(fe)





class FlatEdge:
    
    def __init__(self, edge, face):
        self.edge = edge
        self.face = face
        self.flatten()
        
    def flatten(self):
        edgeEval = self.edge.evaluator
        
        # determine steps for IVP integration using fit strokes        
        (ret, t0, t1) = edgeEval.getParameterExtents()
        (ret, strokes) = edgeEval.getStrokes(t0, t1, fitTolerance);
        
        #(ret, tvec) = edgeEval.getParametersAtPoints(strokes)
        # since getParametersAtPoints is currently broken
        # approximate parameter values at strokes by assuming
        # the curve is constant speed
        d = [0.]
        for idx in range(1, len(strokes)):
            d.append(d[idx-1] + strokes[idx].distanceTo(strokes[idx-1]))

        # parameter value is proportional to distance for constant speed
        tvec = [t0]
        for idx in range(1, len(d)):
            tvec.append(t0 + (t1-t0)*d[idx]/d[-1])

        # initial point on plane is 0,0 and speed is mag(first derivative of curve) in X
        (ret, r_t) = edgeEval.getFirstDerivative(t0)
        x0 = [0., 0., r_t.length, 0.]
        rhsFun = partial(FlatEdge.rhs, self)
        [xOut, err] = ode23(rhsFun, x0, tvec)
        
        self.points = []
        for idx in range(len(xOut)):
            v = xOut[idx]
            self.points.append([v[0], v[1]])
            
        print ("edge done")
 
    # rhs for ODE, state vector is (x, y, x_t, y_t) 
    def rhs(self, t, state):
        state_t = [state[2], state[3], 0., 0.]
        edgeEval = self.edge.evaluator
        faceEval = self.face.evaluator
        
        (ret, p) = edgeEval.getPointAtParameter(t)
        (ret, r_t) = edgeEval.getFirstDerivative(t)
        (ret, r_tt) = edgeEval.getSecondDerivative(t)
        (ret, tangent) = edgeEval.getTangent(t)
        tangent.normalize()
        (ret, curveDir, curveMag) = edgeEval.getCurvature(t)
        curveDir.normalize()
        curvature = curveDir.copy()
        curvature.scaleBy(curveMag)
       
        # TODO check the surface curvature to insure ruled surface? 
        #(ret, sparam) = faceEval.getParameterAtPoint(p)
        #(ret, maxTangent, maxCurvature, minCurvature) = faceEval.getCurvature(sparam)
                
        (ret, surfaceNormal) = faceEval.getNormalAtPoint(p)
        surfaceNormal.normalize()
        tmp = surfaceNormal.crossProduct(tangent)
        curve_geo = curvature.dotProduct(tmp)
        
        A = r_t.dotProduct(r_tt) / r_t.dotProduct(r_t)
        B = curve_geo * r_t.length
        state_t[2] = A * state[2] - B * state[3]
        state_t[3] = A * state[3] + B * state[2]
        return state_t
         