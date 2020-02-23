from flat.raw import RawLoop
import os, pickle, math, statistics, array

if __name__ == "__main__":
    # execute only if run as a script
    dir = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(dir, "flat_save.p")
    raw = pickle.load( open(fname, "rb"))

    for loop in raw:
        print("loop --------------------------------------")
        err = loop.assemble()
        print("closure = ", err)
        print("bbox: ", loop.boundingBox)

    exit()
