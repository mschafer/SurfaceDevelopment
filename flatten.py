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
        (ret, tvec) = edgeEval.getParametersAtPoints(strokes)

        for idx in range(1, len(tvec)):
            h = tvec[idx] - tvec[idx-1]
            #if abs(h) < fitTol*1.e-6