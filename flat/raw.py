import os, math, array, pickle, traceback
from .ode23 import ode23
from functools import partial

fitTolerance = .01 # cm database units

class RawLoop:
    def __init__(self, loop):
        self.edges = []
        self.relAngle = array.array('d', [0])
        for iedge in range(loop.coEdges.count):
            ce = loop.coEdges.item(iedge)
            self.edges.append(RawEdge(ce))

            eeval = ce.edge.evaluator            
            (ret, t0, t1) = eeval.getParameterExtents()
            (ret, tang0) = eeval.getFirstDerivative(t0)
            (ret, tang1) = eeval.getFirstDerivative(t1)
            
            # if reversed, swap tangents and reverse them
            if ce.isOpposedToEdge:
                tang0.scaleBy(-1.)
                tang1.scaleBy(-1.)
                tang0, tang1 = tang1, tang0
            
            if iedge > 0:
                self.relAngle.append(lastTangent.angleTo(tang0))
            else:
                startTang = tang0
            
            # tangent at end (in loop direction) for relAngle next time around
            lastTangent = tang1

        self.relAngle[0] = tang1.angleTo(startTang)

class RawEdge:
    def __init__(self, coEdge):
        self.needsReverse = coEdge.isOpposedToEdge
        self.length3d = coEdge.edge.length
        self.flatten(coEdge.edge, coEdge.loop.face)
        
    def flatten(self, edge, face):
        edgeEval = edge.evaluator
        
        # determine steps for IVP integration using fit strokes        
        (ret, t0, t1) = edgeEval.getParameterExtents()
        (ret, strokes) = edgeEval.getStrokes(t0, t1, fitTolerance)
        

        # getParameterAtPoints thread is here:
        # https://forums.autodesk.com/t5/fusion-360-api-and-scripts/getparameteratpoint-returning-incorrect-value/m-p/8548381/highlight/true#M7248
        
        #(ret, tvec) = edgeEval.getParametersAtPoints(strokes)
        # since getParametersAtPoints is currently broken
        # approximate parameter values at strokes by assuming
        # the curve is constant speed
        self.d = array.array('d', [0.])
        for idx in range(1, len(strokes)):
            self.d.append(self.d[idx-1] + strokes[idx].distanceTo(strokes[idx-1]))

        # parameter value is proportional to distance for constant speed
        tvec = [t0]
        for idx in range(1, len(self.d)):
            tvec.append(t0 + (t1-t0)*self.d[idx]/self.d[-1])

        # initial point on plane is 0,0 and speed is mag(first derivative of curve) in X
        (ret, r_t) = edgeEval.getFirstDerivative(t0)
        x0 = [0., 0., r_t.length, 0.]
        rhsFun = partial(RawEdge.rhs, self, edge, face)
        [xOut, err] = ode23(rhsFun, x0, tvec)

        # tangent = math.atan2(dy, dx)

        self.points = []
        self.tangents = []
        for idx in range(len(xOut)):
            v = xOut[idx]
            self.points.append([v[0], v[1]])
            self.tangents.append([v[2], v[3]])
            
    # rhs for ODE, state vector is (x, y, x_t, y_t) 
    def rhs(self, edge, face, t, state):
        state_t = [state[2], state[3], 0., 0.]
        edgeEval = edge.evaluator
        faceEval = face.evaluator
        
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

    def reverse(self):
        self.d.reverse()
        self.points.reverse()

        # 
        self.tangents.reverse()
        for i, t in enumerate(self.tangents):
            t[0] = -1. * t[0]
            t[1] = -1. * t[1]
        
        self.needsReverse = (not self.needsReverse)

    def rotate(self, theta):
        costh = math.cos(theta)
        sinth = math.sin(theta)
        idx = 0
        for pt in self.points:
            xn = pt[0]*costh - pt[1]*sinth
            yn = pt[0]*sinth + pt[1]*costh
            pt[0] = xn
            pt[1] = yn

            # tangents
            tt = self.tangents[idx]
            xtn = tt[0]*costh - tt[1]*sinth
            ytn = tt[0]*sinth + tt[1]*costh
            tt[0] = xtn
            tt[1] = ytn

            idx = idx + 1

    def translateTo(self, x, y):
        dx = x - self.points[0][0]
        dy = y - self.points[0][1]
        for pt in self.points:
            pt[0] = pt[0] + dx
            pt[1] = pt[1] + dy

    def calcLength(self):
        self.l = array.array('d', [0.])
        for i in range(1, len(self.points)):
            p0 = self.points[i-1]
            p1 = self.points[i]
            self.l.append(self.l[i-1] + math.hypot(p1[0]-p0[0], p1[1]-p0[1]))
        return self.l[-1]

    def correctLength(self):
        tot = self.length3d - self.calcLength()
        for i in range(1, len(self.points)):
            pt = self.points[i]
            tang = self.tangents[i]
            tangLen = math.hypot(tang[0], tang[1])
            delta = self.l[i] / self.l[-1] * tot
            pt[0] = pt[0] + delta * tang[0] / tangLen
            pt[1] = pt[1] + delta * tang[1] / tangLen

    def setStart(self, p0, tang0):
        th1 = math.atan2(tang0[1], tang0[2])
        th0 = math.atan2(self.tangents[0][1], self.tangents[0][0])
        self.rotate(th1 - th0)
        self.translateTo(p0[0], p0[1])