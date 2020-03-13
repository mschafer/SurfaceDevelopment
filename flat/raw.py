import os, math, array, pickle, traceback, statistics
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

    def assemble(self):
        # stretch edges to match length in 3d and reverse if needed
        for edge in self.edges:
            edge.correctLength()
            if edge.needsReverse:
                edge.reverse()
        
        # rotate edges to match corner angles in 3d
        for iedge in range(1, len(self.edges)):
            targetAngle = self.relAngle[iedge]
            endTang = self.edges[iedge-1].tangents[-1]
            endAngle = math.atan2(endTang[1], endTang[0])
            startTang = self.edges[iedge].tangents[0]
            startAngle = math.atan2(startTang[1], startTang[0])
            actualAngle = startAngle - endAngle
            rAngle = targetAngle - actualAngle
            self.edges[iedge].rotate(rAngle)

        # translate edges so they are end to end
        for iedge in range(1, len(self.edges)):
            endPt = self.edges[iedge-1].points[-1]
            self.edges[iedge].translateTo(endPt[0], endPt[1])

        # orient the shape close to vertical for tiling in 2d
        self.orientVertical()

        self.boundingBox = self.calcBoundingBox()

        # return the close error
        startPt = self.edges[0].points[0]
        endPt = self.edges[-1].points[-1]
        return math.hypot(endPt[0] - startPt[0], endPt[1] - startPt[1])

    def rotate(self, theta):
        for edge in self.edges:
            edge.rotate(theta)

    def calcBoundingBox(self):
        bb = None
        for edge in self.edges:
            bbe = edge.calcBoundingBox()
            if bb == None:
                bb = bbe
            else:
                bb[0] = min(bb[0], bbe[0])
                bb[1] = min(bb[1], bbe[1])
                bb[2] = max(bb[2], bbe[2])
                bb[3] = max(bb[3], bbe[3])
        return bb
    
    def translateBy(self, dx, dy):
        for edge in self.edges:
            edge.translateBy(dx, dy)

    def orientVertical(self):
        x = array.array('d', [])
        y = array.array('d', [])
        for edge in self.edges:
            xe, ye = edge.xy()
            x.extend(xe)
            y.extend(ye)

        xmean = statistics.mean(x)
        ymean = statistics.mean(y)
        xy = 0.
        xx = 0.
        for i in range(len(x)):
            xy = xy + (x[i] - xmean)*(y[i] - ymean)
            xx = xx + (x[i] - xmean)*(x[i] - xmean)

        angle = math.atan2(xy, xx)
        pi = 4. * math.atan(1.)
        self.rotate(pi/2. - angle)
        bb = self.calcBoundingBox()
        self.translateBy(-bb[0], -bb[1])

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

        # an error will occur if either endpoint is outside of range by eps so squeeze end in by a tiny amount
        dt = 1.e-13 * (tvec[-1] - tvec[0])
        tvec[0] = t0 + dt
        tvec[-1] = t1 - dt 

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
        self.translateBy(dx, dy)

    def translateBy(self, dx, dy):
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

    def xy(self):
        x = array.array('d', [])
        y = array.array('d', [])
        for pt in self.points:
            x.append(pt[0])
            y.append(pt[1])
        return x, y

    def calcBoundingBox(self):
        x, y = self.xy()
        bbox = array.array('d', [0., 0., 0., 0.])
        bbox[0] = min(x)
        bbox[1] = min(y)
        bbox[2] = max(x)
        bbox[3] = max(y)
        return bbox