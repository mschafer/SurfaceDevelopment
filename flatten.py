import adsk.core, adsk.fusion, adsk.cam, traceback
import os, math


class FlatEdge:
    
    def __init__(self, edge, face):
        self.edge = edge
        self.face = face
        
    def flatten(self):
        edgeEval = self.edge.evaluator
        faceEval = self.face.evaluator
        fitTol = .001 # cm database units
        
        (ret, t0, t1) = edgeEval.getParameterExtents()
        (ret, strokes) = edgeEval.getStrokes(t0, t1, fitTol);
        #(ret, tvec) = edgeEval.getParametersAtPoints(strokes)


        # since getParametersAtPoints is currently broken
        # approximate parameter values at strokes by assuming
        # the curve is constant speed
        d = [0.]
        for idx in range(1, len(strokes)):
            d.append(d[idx-1] + strokes[idx].distanceTo(strokes[idx-1]))

        tvec = [t0]
        for idx in range(1, len(d)):
            tvec.append(t0 + (t1-t0)*d[idx]/d[-1])
            
        for t in tvec:
            (ret, p) = edgeEval.getPointAtParameter(t)
            (ret, r_t) = edgeEval.getFirstDerivative(t)
            (ret, r_tt) = edgeEval.getSecondDerivative(t)
            (ret, tangent) = edgeEval.getTangent(t)
            (ret, curvature, curveMag) = edgeEval.getCurvature(t)
            ret = curvature.scaleBy(curveMag)
            
            (ret, sparam) = faceEval.getParameterAtPoint(p)
            (ret, maxTangent, maxCurvature, minCurvature) = faceEval.getCurvature(sparam)
            (ret, surfaceNormal) = faceEval.getNormalAtPoint(p)
            tmp = surfaceNormal.crossProduct(tangent)
            curve_geo = curvature.dotProduct(tmp)
 