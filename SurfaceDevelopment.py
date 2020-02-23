#Author-Marc Schafer
#Description-Flattens developable faces.
import adsk.core, adsk.fusion, adsk.cam, traceback
import os, sys

#get the path of add-in
my_addin_path = os.path.dirname(os.path.realpath(__file__)) 
print(my_addin_path)

#add the path to the searchable path collection
if not my_addin_path in sys.path:
   sys.path.append(my_addin_path) 

import math, glob, pickle

try:
    from .flatten import FlatLoop
    from flat.raw import RawLoop
except Exception as e:
    print(e)

_app = None
_ui  = None

# global set of event handlers to keep them referenced for the duration of the command
_handlers = []

class FlattenCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            command = args.firingEvent.sender
            inputs = command.commandInputs

            # faces to flatten
            flattened = []
            input0 = inputs[0]
            for isel in range(input0.selectionCount):
                facesel = input0.selection(isel)
                face = facesel.entity
                loops = face.loops
                outerLoop = loops[0]
                raw = RawLoop(outerLoop)
                raw.assemble()
                flattened.append(raw)

            saveRaw(flattened)
            input1 = inputs[1]     # sketch
            sel1 = input1.selection(0)
            plane = sel1.entity
            product = _app.activeProduct
            design = adsk.fusion.Design.cast(product)
            root = design.rootComponent
            sketch = root.sketches.add(plane)
            lines = sketch.sketchCurves.sketchLines

            # add all the flattened loops to a sketch spaced out along the x axis
            x = 0.
            y = 0.
            for loop in flattened:
                dx = x - loop.boundingBox[0]
                dy = y - loop.boundingBox[1]

                for edge in loop.edges:
                    xe, ye = edge.xy()
                    xe = [pxe+dx for pxe in xe]
                    ye = [pye+dy for pye in ye]
                    addSketchSpline(xe, ye, sketch)
                
                x = x + loop.boundingBox[2] + 1.

        except:
            unimport()
            if _ui:
                _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

class FlattenCommandDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # when the command is done, terminate the script
            # this will release all globals which will remove all event handlers
            adsk.terminate()
            unimport()
        except:
            if _ui:
                _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

class FlattenValidateInputHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()
       
    def notify(self, args):
        try:
            args.areInputsValid = True

        except:
            if _ui:
                _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class FlattenCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # Get the command that was created.
            cmd = adsk.core.Command.cast(args.command)

            # Connect to the command execute event.
            onExecute = FlattenCommandExecuteHandler()
            cmd.execute.add(onExecute)
            _handlers.append(onExecute)

            # Connect to the command destroyed event.
            onDestroy = FlattenCommandDestroyHandler()
            cmd.destroy.add(onDestroy)
            _handlers.append(onDestroy)


            #onValidateInput = FlattenValidateInputHandler()
            #cmd.validateInputs.add(onValidateInput)
            #handlers.append(onValidateInput)
            
            #define the inputs
            inputs = cmd.commandInputs
            i0 = inputs.addSelectionInput('FlattenFaces', 'Faces to flatten', 'Please select faces to flatten')
            i0.setSelectionLimits(1, 0)
            i0.addSelectionFilter(adsk.core.SelectionCommandInput.Faces)
            
            #i1 = inputs.addSelectionInput('Sketch', 'Flattened Sketch', 'Sketch to add flattened faces to')
            #i1.addSelectionFilter(adsk.core.SelectionCommandInput.Sketches)

            i1 = inputs.addSelectionInput('ConstPlane', 'Construction Plane', 'Please select a construction plane')
            i1.addSelectionFilter(adsk.core.SelectionCommandInput.ConstructionPlanes)
            i1.addSelectionFilter(adsk.core.SelectionCommandInput.RootComponents)

        except:
            if _ui:
                _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

def run(context):
    try:
        global _app, _ui
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        # Get the existing command definition or create it if it doesn't already exist.
        cmdDef = _ui.commandDefinitions.itemById('FlattenCmdDef')
        if not cmdDef:
            cmdDef = _ui.commandDefinitions.addButtonDefinition('FlattenCmdDef', 'Flatten Command', 'Flatten tooltip')

            # Connect to the command created event.
            # put under the if above to prevent multiple buttons when debugging?
            onCommandCreated = FlattenCommandCreatedHandler()
            cmdDef.commandCreated.add(onCommandCreated)
            _handlers.append(onCommandCreated)

        # Execute the command definition.
        inputs = adsk.core.NamedValues.create()
        cmdDef.execute(inputs)

        # Prevent this module from being terminated when the script returns, because we are waiting for event handlers to fire.
        adsk.autoTerminate(False)

    except:
        if _ui:
            _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


def addSketchSpline(xe, ye, sketch):
    points = adsk.core.ObjectCollection.create()
    for i in range(len(xe)):
        x = xe[i]
        y = ye[i]
        point = adsk.core.Point3D.create(x, y, 0.0)
        points.add(point)

    sketch.sketchCurves.sketchFittedSplines.add(points)


# unimport: delete the modules introduced by this Addin from the python cache.
def unimport():

    # Fetch the absolute path of this Addin's directory
    cwd = os.path.abspath(os.path.dirname(__file__))

    # walk through python files in the directory, and remove them from the
    # python module cache.
    for thisFile in glob.glob(cwd + "/*.py"):
        thisModule = str(os.path.basename(thisFile).replace(".py", ""))
        try:
            del sys.modules[thisModule]
        except (AttributeError, KeyError):
            # Key will not exist if a .py file wasn't imported; Attribute will be wrong if it isn't a module
            pass

def saveRaw(raw):
    # pickle raw flattened data
    # path to folder containing this module
    dir = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(dir, "flat_save.p")    
    pickle.dump(raw, open( fname, "wb" ))
