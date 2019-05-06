import adsk.core, adsk.fusion, adsk.cam, traceback
import os, math
from .ode23 import ode23
from functools import partial

fitTolerance = .1 # cm database units

class FlatLoop:
    def __init__(self, loop):
        flatEdges = []
        tangents = [] #tangents at the end of each edge
        # coEdges are ordered head to tail CCW around outside loop (CW on inner loop)
        for iedge in range(loop.coEdges.count):
            ce = loop.coEdges.item(iedge)
            eeval = ce.edge.evaluator            
            print("opposed:", ce.isOpposedToEdge)
            (ret, t0, t1) = eeval.getParameterExtents()
            (ret, tang0) = eeval.getFirstDerivative(t0)
            (ret, tang1) = eeval.getFirstDerivative(t1)
            (ret, sp, ep) = eeval.getEndPoints()
            print("start: ", sp.x, sp.y, sp.z)
            print("tang:  ", tang0.x, tang0.y, tang0.z)
            print("end:   ", ep.x, ep.y, ep.z)
            print("tang:  ", tang1.x, tang1.y, tang1.z)
            print("-------------------------------------------------")
            
            
            
            
            
            
#            
#            fe = FlatEdge(ce.edge, loop.face, ce.isOpposedToEdge)
#            flatEdges.append(fe)
#            
#            eeval = ce.edge.evaluator
#            (ret, t0, t1) = eeval.getParameterExtents()
#            if ce.isOpposedToEdge:
#                (ret, tangent1) = eeval.getFirstDerivative(t0)
#                tangent1.scaleBy(-1.)
#                
#            else:
#                (ret, tangent1) = eeval.getFirstDerivative(t1)
#            tangents.append(tangent1)
            
        for tt in tangents:
            print(tt.x, tt.y, tt.z)
            
        # edges are flattened to origin and tangent to x axis
        # translate and rotate each edge to correct relative orientation
        for iedge in range(1, len(flatEdges)):
            # relative angle between the end of this edge and the previous one
            relAngle = tangents[iedge-1].angleTo(tangents[iedge])
            flatEdges[iedge].rotate(flatEdges[iedge-1].tangents[1] + relAngle)
            
            # translate to endpoint of previous edge
            x0 = flatEdges[iedge-1].points[-1][0]
            y0 = flatEdges[iedge-1].points[-1][1]
            flatEdges[iedge].translateTo(x0, y0)
            
        for fe in flatEdges:
            print(fe.points[0])
            print(fe.points[-1])


class FlatEdge:
    
    def __init__(self, edge, face, opposedToEdge):
        self.edge = edge
        self.face = face
        self.opposedToEdge = opposedToEdge
        self.flatten()
        
    def flatten(self):
        edgeEval = self.edge.evaluator
        
        # determine steps for IVP integration using fit strokes        
        (ret, t0, t1) = edgeEval.getParameterExtents()
        (ret, strokes) = edgeEval.getStrokes(t0, t1, fitTolerance)
        
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
        self.tangents = [0.] # angle of tangent at start and end
        for idx in range(len(xOut)):
            v = xOut[idx]
            self.points.append([v[0], v[1]])
            
        self.tangents.append(math.atan2(xOut[-1][3], xOut[-1][2]))
        if self.opposedToEdge:
            self.points.reverse()
            self.translateTo(0, 0)
            self.tangents.reverse()
            self.tangents[0] = self.tangents[0] + math.radians(180.)
            self.tangents[1] = self.tangents[1] + math.radians(180.)
            
        print ("edge flattened")
    
    # translate the entire flattened edge so that the first point is at x,y
    def translateTo(self, x, y):
        dx = x - self.points[0][0]
        dy = y - self.points[0][1]
        for pt in self.points:
            pt[0] = pt[0] + dx
            pt[1] = pt[1] + dy
    
    # rotate the entire flattened edge so the first segment is at the given angle
    def rotate(self, theta):
        self.tangents[0] = self.tangents[0] + theta
        self.tangents[1] = self.tangents[1] + theta
        for pt in self.points:
            xn = pt[0]*math.cos(theta) - pt[1]*math.sin(theta)
            yn = pt[0]*math.sin(theta) + pt[1]*math.cos(theta)
            pt[0] = xn
            pt[1] = yn
            
 
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
         