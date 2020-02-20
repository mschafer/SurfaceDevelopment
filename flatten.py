import adsk.core, adsk.fusion, adsk.cam, traceback
import os, math, array
from .ode23 import ode23
from functools import partial

fitTolerance = .01 # cm database units

class FlatLoop:
    def __init__(self, loop):
        self.flatEdges = []
        relAngle = []
        raw = []
        firstTangent = adsk.core.Vector3D.create()
        lastTangent = adsk.core.Vector3D.create()
        # coEdges are ordered head to tail CCW around outside loop (CW on inner loop)
        for iedge in range(loop.coEdges.count):
            ce = loop.coEdges.item(iedge)
            raw.append(RawEdge(ce))
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
            
            # tangent at beginning (in loop direction) of this edge
            if ce.isOpposedToEdge:
                firstTangent = tang1
                firstTangent.scaleBy(-1.)
            else:
                firstTangent = tang0
            
            if iedge > 0:
                relAngle.append(lastTangent.angleTo(firstTangent))
            else:
                relAngle.append(0.)
            
            # tangent at end (in loop direction) for relAngle next time around
            # in the direction of the loop
            if ce.isOpposedToEdge:
                lastTangent = tang0
                lastTangent.scaleBy(-1.)
            else:
                lastTangent = tang1
                                            
            # flatten each edge around the loop
            # use the edge instead of coEdge becuase we need the 3d evaluator
            fe = FlatEdge(ce.edge, loop.face, ce.isOpposedToEdge)
            self.flatEdges.append(fe)
            
        # edges are flattened to origin and tangent to x axis
        # attach the beginning of the next edge to the end of the previous one
        # rotate so the angle between the two matches that of the edges prior to flattening
        for iedge in range(1, len(self.flatEdges)):
            endAngle = self.flatEdges[iedge-1].tangents[1] # angle at end of previous edge
            print("endAngle: ", math.degrees(endAngle))
            initAngle = self.flatEdges[iedge].tangents[0]
            print("initAngle: ", math.degrees(initAngle))
            print ("rel: ", math.degrees(relAngle[iedge]))
            self.flatEdges[iedge].rotate(endAngle + relAngle[iedge] - initAngle)
            
            # translate to endpoint of previous edge
            x0 = self.flatEdges[iedge-1].points[-1][0]
            y0 = self.flatEdges[iedge-1].points[-1][1]
            self.flatEdges[iedge].translateTo(x0, y0)
            
        print("-------------------------------------------------")
        for fe in self.flatEdges:
            print(fe.points[0])
            print(fe.points[-1])

        self.calcBoundingBox()
        print("-------------------------------------------------")

    # calculate the axis aligned bounding box of the flattened loop
    def calcBoundingBox(self):
        self.boundingBox = [0., 0., 0., 0.]
        for fe in self.flatEdges:
            b = fe.boundingBox()
            self.boundingBox[0] = min(self.boundingBox[0], b[0])
            self.boundingBox[1] = min(self.boundingBox[1], b[1])
            self.boundingBox[2] = max(self.boundingBox[2], b[2])
            self.boundingBox[3] = max(self.boundingBox[3], b[3])

    def rotate(self, theta):
        for fe in self.flatEdges:
            fe.rotate(theta)

        self.calcBoundingBox()

    def translateBy(self, dx, dy):
        for fe in self.flatEdges:
            fe.translateBy(dx, dy)

        self.boundingBox[0] = self.boundingBox[0] + dx
        self.boundingBox[1] = self.boundingBox[1] + dy
        self.boundingBox[2] = self.boundingBox[2] + dx
        self.boundingBox[3] = self.boundingBox[3] + dy


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
        

        # getParameterAtPoints thread is here:
        # https://forums.autodesk.com/t5/fusion-360-api-and-scripts/getparameteratpoint-returning-incorrect-value/m-p/8548381/highlight/true#M7248
        
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
            
        print ("------------- edge flattened ----------------")
        print("start: ", self.points[0])
        print("tang:  ", self.tangents[0])
        print("end:   ", self.points[-1])
        print("tang:  ", self.tangents[-1])


    # translate the entire flattened edge so that the first point is at x,y
    def translateTo(self, x, y):
        dx = x - self.points[0][0]
        dy = y - self.points[0][1]
        self.translateBy(dx, dy)

    def translateBy(self, dx, dy):
        for pt in self.points:
            pt[0] = pt[0] + dx
            pt[1] = pt[1] + dy
    
    # rotate the entire flattened edge by the given angle
    def rotate(self, theta):
        self.tangents[0] = self.tangents[0] + theta
        self.tangents[1] = self.tangents[1] + theta
        for pt in self.points:
            xn = pt[0]*math.cos(theta) - pt[1]*math.sin(theta)
            yn = pt[0]*math.sin(theta) + pt[1]*math.cos(theta)
            pt[0] = xn
            pt[1] = yn

    # returns the bounding box as a list of floats [xmin, ymin, xmax, ymax]
    def boundingBox(self):
        bbox = [0., 0., 0., 0.]
        for pt in self.points:
            bbox[0] = min(bbox[0], pt[0])
            bbox[1] = min(bbox[1], pt[1])
            bbox[2] = max(bbox[2], pt[0])
            bbox[3] = max(bbox[3], pt[1])
        return bbox
            
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


class RawLoop:
    def __init__(self, loop):
        self.edges = []
        for iedge in range(loop.coEdges.count):
            ce = loop.coEdges.item(iedge)
            self.edges.append(RawEdge(ce))

class RawEdge:
    def __init__(self, coEdge):
        self.needsReverse = coEdge.isOpposedToEdge
        self.length3d = coEdge.edge.length

        eeval = coEdge.edge.evaluator            
        (ret, sp, ep) = eeval.getEndPoints()
        self.start3d = array.array('d', [sp.x, sp.y, sp.z])
        self.end3d = array.array('d', [ep.x, ep.y, ep.z])

        (ret, t0, t1) = eeval.getParameterExtents()
        (ret, tang0) = eeval.getFirstDerivative(t0)
        self.startTang3d = array.array('d', [tang0.x, tang0.y, tang0.z])
        (ret, tang1) = eeval.getFirstDerivative(t1)
        self.startTang3d = array.array('d', [tang1.x, tang1.y, tang1.z])

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
        rhsFun = partial(RawEdge.rhs, self, edge, face)
        [xOut, err] = ode23(rhsFun, x0, tvec)

        self.tangents = [0.] # angle of tangent at start and end
        self.tangents.append(math.atan2(xOut[-1][3], xOut[-1][2]))

        self.points = []
        self.slopes = []
        for idx in range(len(xOut)):
            v = xOut[idx]
            self.points.append([v[0], v[1]])
            self.slopes.append([v[2], v[3]])
            
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
         