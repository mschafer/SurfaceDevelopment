#Author-Marc Schafer
#Description-Flattens developable faces.

import adsk.core, adsk.fusion, adsk.cam, traceback, math

try:
    from .flatten import FlatLoop
except Exception as e:
    print(e)


# global set of event handlers to keep them referenced for the duration of the command
handlers = []
app = adsk.core.Application.get()
if app:
    ui  = app.userInterface

product = app.activeProduct
design = adsk.fusion.Design.cast(product)

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
                fl = FlatLoop(outerLoop)
                flattened.append(fl)

            input1 = inputs[1]     # sketch
            sel1 = input1.selection(0)
            plane = sel1.entity
            root = design.rootComponent
            sketch = root.sketches.add(plane)
            lines = sketch.sketchCurves.sketchLines

            # add all the flattened loops to a sketch spaced out along the x axis
            x = 0.
            y = 0.
            for fl in flattened:
                dx = x - fl.boundingBox[0]
                dy = y - fl.boundingBox[1]
                fl.translateBy(dx, dy)
                addSketchSpline(fl, sketch)
                x = fl.boundingBox[2] + 1.

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

class FlattenCommandDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # when the command is done, terminate the script
            # this will release all globals which will remove all event handlers
            adsk.terminate()
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

class FlattenValidateInputHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()
       
    def notify(self, args):
        try:
            args.areInputsValid = True

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class FlattenCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            cmd = args.command
            onExecute = FlattenCommandExecuteHandler()
            cmd.execute.add(onExecute)
            onDestroy = FlattenCommandDestroyHandler()
            cmd.destroy.add(onDestroy)

            #onValidateInput = FlattenValidateInputHandler()
            #cmd.validateInputs.add(onValidateInput)
            # keep the handler referenced beyond this function
            handlers.append(onExecute)
            handlers.append(onDestroy)
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
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

def run(context):
    try:
        
        title = 'Flatten'
        if not design:
            ui.messageBox('No active Fusion design', title)
            return

        # delete the command if it already exists otherwise the dialog contains multiple copies of all the buttons
        # this seems to happen when the script errors out in the debugger
        commandDefinitions = ui.commandDefinitions
        cmdDef = commandDefinitions.itemById('FlattenCmdDef')
        if cmdDef:
            cmdDef.deleteMe()
            handlers = []

        # create a command
        cmdDef = ui.commandDefinitions.addButtonDefinition('FlattenCmdDef', 'Flatten Command', 'Flatten tooltip')
        onCommandCreated = FlattenCommandCreatedHandler()
        cmdDef.commandCreated.add(onCommandCreated)
        # keep the handler referenced beyond this function
        handlers.append(onCommandCreated)

        inputs = adsk.core.NamedValues.create()
        cmdDef.execute(inputs)

        # prevent this module from being terminate when the script returns, because we are waiting for event handlers to fire
        adsk.autoTerminate(False)

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))



def addSketchSpline(flatLoop, sketch):
    for fe in flatLoop.flatEdges:
        points = adsk.core.ObjectCollection.create()
        for pt in fe.points:
            x = pt[0]
            y = pt[1]
            point = adsk.core.Point3D.create(x, y, 0.0)
            points.add(point)
    
        sketch.sketchCurves.sketchFittedSplines.add(points)
