from flat.raw import RawLoop
import os, pickle, math

if __name__ == "__main__":
    # execute only if run as a script
    dir = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(dir, "flat_save.p")
    raw = pickle.load( open(fname, "rb"))
    for i in range(len(raw)):
        print("loop ", i, "has ", len(raw[i].edges), "edges ------------------------------------")
        print("corners ", raw[i].relAngle)
        for e in range(len(raw[i].edges)):
            edge = raw[i].edges[e]
            edge.correctLength()
            print ("l3d = ", edge.length3d, "\t l2d = ", edge.calcLength())

    # reverse as needed
    il = 0
    for loop in raw:
        ie = 0
        for edge in loop.edges:
            if edge.needsReverse:
                print("reversing: ", il, ie)
                edge.reverse()
                ie = ie + 1
        il = il + 1

    # roate edges to match 3d corner angles
    for loop in raw:
        for iedge in range(1, len(loop.edges)):
            targetAngle = loop.relAngle[iedge]
            endTang = loop.edges[iedge-1].tangents[-1]
            endAngle = math.atan2(endTang[1], endTang[0])
            startTang = loop.edges[iedge].tangents[0]
            startAngle = math.atan2(startTang[1], startTang[0])
            actualAngle = startAngle - endAngle
            rAngle = targetAngle - actualAngle
            loop.edges[iedge].rotate(rAngle)

    # translate the edges end to end
    for loop in raw:
        for iedge in range(1, len(loop.edges)):
            endPt = loop.edges[iedge-1].points[-1]
            loop.edges[iedge].translateTo(endPt[0], endPt[1])
        startPt = loop.edges[0].points[0]
        endPt = loop.edges[-1].points[-1]
        print("close error = ", endPt[0] - startPt[0], endPt[1] - startPt[1])

