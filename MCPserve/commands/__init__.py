# Here you define the commands that will be added to your add-in.

# Import the modules corresponding to the commands you created.
from .commandDialog import entry as commandDialog
from .paletteShow import entry as paletteShow
from .paletteSend import entry as paletteSend
from . import MCPServerCommand

# Add your imported modules to this list.
# Fusion will automatically call the start() and stop() functions.
commands = [
    MCPServerCommand
]


# Assumes you defined a "start" function in each of your modules.
# The start function will be run when the add-in is started.
def start():
    for command in commands:
        command.start()


# Assumes you defined a "stop" function in each of your modules.
# The stop function will be run when the add-in is stopped.
def stop():
    for command in commands:
        command.stop()