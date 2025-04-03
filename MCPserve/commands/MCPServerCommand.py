import adsk.core
import adsk.fusion
import os
import sys
import traceback
import threading
import time
import json
import importlib.util
import site
from pathlib import Path
import asyncio
import tempfile

from ..lib import fusionAddInUtils as futil

# Global variables
app = adsk.core.Application.get()
ui = app.userInterface
server_thread = None
server_running = False

# Global storage for resources, tools, and prompts
resources = {}
tools = {}
prompts = {}

# Check if MCP package is installed
def check_mcp_installed():
    try:
        import mcp
        print(f"Found MCP package at: {mcp.__file__}")
        return True
    except ImportError:
        return False

# Function to run MCP server
def run_mcp_server():
    try:
        # Import required MCP modules
        import mcp
        from mcp.server.fastmcp import FastMCP
        
        # Create the MCP server
        fusion_mcp = FastMCP("Fusion 360 MCP Server")
        
        # Define resources
        @fusion_mcp.resource("active-document-info")
        def get_active_document_info():
            """Get information about the active document in Fusion 360."""
            try:
                doc = app.activeDocument
                if doc:
                    return {
                        "name": doc.name,
                        "path": doc.dataFile.name if doc.dataFile else "Unsaved",
                        "type": doc.documentType
                    }
                else:
                    return {"error": "No active document"}
            except:
                return {"error": traceback.format_exc()}
        
        @fusion_mcp.resource("design-structure")
        def get_design_structure():
            """Get the structure of the active design in Fusion 360."""
            try:
                doc = app.activeDocument
                if not doc:
                    return {"error": "No active document"}
                
                if doc.documentType != adsk.core.DocumentTypes.FusionDesignDocumentType:
                    return {"error": "Not a Fusion design document"}
                
                design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
                if not design:
                    return {"error": "No design in document"}
                
                root_comp = design.rootComponent
                
                def get_component_data(component):
                    data = {
                        "name": component.name,
                        "bodies": [body.name for body in component.bodies],
                        "sketches": [sketch.name for sketch in component.sketches],
                        "occurrences": []
                    }
                    
                    for occurrence in component.occurrences:
                        data["occurrences"].append({
                            "name": occurrence.name,
                            "component": occurrence.component.name
                        })
                    
                    return data
                
                return {
                    "design_name": design.name,
                    "root_component": get_component_data(root_comp)
                }
            except:
                return {"error": traceback.format_exc()}
        
        @fusion_mcp.resource("parameters")
        def get_parameters():
            """Get the parameters of the active design in Fusion 360."""
            try:
                doc = app.activeDocument
                if not doc:
                    return {"error": "No active document"}
                
                if doc.documentType != adsk.core.DocumentTypes.FusionDesignDocumentType:
                    return {"error": "Not a Fusion design document"}
                
                design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
                if not design:
                    return {"error": "No design in document"}
                
                params = []
                for param in design.allParameters:
                    params.append({
                        "name": param.name,
                        "value": param.value,
                        "expression": param.expression,
                        "unit": param.unit,
                        "comment": param.comment
                    })
                
                return {"parameters": params}
            except:
                return {"error": traceback.format_exc()}
        
        # Define tools
        @fusion_mcp.tool()
        def message_box(message: str) -> str:
            """Display a message box in Fusion 360."""
            try:
                def show_message():
                    ui.messageBox(message)
                app.executeInApplicationContext(show_message)
                return "Message displayed successfully"
            except:
                return f"Error displaying message: {traceback.format_exc()}"
        
        @fusion_mcp.tool()
        def create_new_sketch(plane_name: str) -> str:
            """Create a new sketch on the specified plane."""
            try:
                def create_sketch():
                    doc = app.activeDocument
                    if not doc:
                        return "No active document"
                    
                    if doc.documentType != adsk.core.DocumentTypes.FusionDesignDocumentType:
                        return "Not a Fusion design document"
                    
                    design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
                    if not design:
                        return "No design in document"
                    
                    root_comp = design.rootComponent
                    
                    # Find the plane
                    construction_planes = root_comp.constructionPlanes
                    sketch_plane = None
                    
                    # Check if the plane_name is a standard plane (XY, YZ, XZ)
                    if plane_name == "XY":
                        sketch_plane = root_comp.xYConstructionPlane
                    elif plane_name == "YZ":
                        sketch_plane = root_comp.yZConstructionPlane
                    elif plane_name == "XZ":
                        sketch_plane = root_comp.xZConstructionPlane
                    else:
                        # Try to find a construction plane with the given name
                        for i in range(construction_planes.count):
                            plane = construction_planes.item(i)
                            if plane.name == plane_name:
                                sketch_plane = plane
                                break
                    
                    if not sketch_plane:
                        return f"Could not find plane: {plane_name}"
                    
                    # Create the sketch
                    sketches = root_comp.sketches
                    sketch = sketches.add(sketch_plane)
                    sketch.name = f"Sketch_MCP_{int(time.time()) % 10000}"
                    
                    return f"Sketch created: {sketch.name}"
                
                result = app.executeInApplicationContext(create_sketch)
                return result
            except:
                return f"Error creating sketch: {traceback.format_exc()}"
        
        @fusion_mcp.tool()
        def create_parameter(name: str, expression: str, unit: str = "", comment: str = "") -> str:
            """Create a new parameter in the active design."""
            try:
                def create_param():
                    doc = app.activeDocument
                    if not doc:
                        return "No active document"
                    
                    if doc.documentType != adsk.core.DocumentTypes.FusionDesignDocumentType:
                        return "Not a Fusion design document"
                    
                    design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
                    if not design:
                        return "No design in document"
                    
                    # Check if the parameter already exists
                    try:
                        existing_param = design.userParameters.itemByName(name)
                        if existing_param:
                            # Update the parameter
                            existing_param.expression = expression
                            if unit:
                                existing_param.unit = unit
                            if comment:
                                existing_param.comment = comment
                            return f"Parameter updated: {name}"
                    except:
                        # Parameter doesn't exist, create it
                        param = design.userParameters.add(name, adsk.core.ValueInput.createByString(expression), unit, comment)
                        return f"Parameter created: {name}"
                
                result = app.executeInApplicationContext(create_param)
                return result
            except:
                return f"Error creating parameter: {traceback.format_exc()}"
        
        # Define prompts
        @fusion_mcp.prompt()
        def create_sketch_prompt() -> str:
            """Prompt template for creating a sketch."""
            return """
You are a Fusion 360 sketch assistant. Create a sketch based on the user's description.

Use these Fusion 360 tools:
1. create_new_sketch - Creates a new sketch on a specified plane
2. get_active_document_info - Gets information about the active document
3. message_box - Displays a message box

Steps to create a sketch:
1. Create a new sketch using create_new_sketch
2. Use appropriate sketch tools to draw the geometry
3. Notify the user when complete

Example:
User: Create a circle on the XY plane
Assistant: I'll create a circle on the XY plane.
(calls create_new_sketch with plane_name="XY")
(calls message_box with message="Circle sketch created successfully")
"""
        
        @fusion_mcp.prompt()
        def parameter_setup_prompt() -> str:
            """Prompt template for setting up parameters."""
            return """
You are a Fusion 360 parameter assistant. Create parameters based on the user's description.

Use these Fusion 360 tools:
1. create_parameter - Creates a new parameter with name, expression, unit, and comment
2. get_parameters - Gets a list of all parameters in the design
3. message_box - Displays a message box

Steps to create parameters:
1. Use get_parameters to check existing parameters
2. Create or update parameters using create_parameter
3. Notify the user when complete

Example:
User: Create a parameter for width with value 10 mm
Assistant: I'll create a width parameter.
(calls create_parameter with name="width", expression="10 mm", unit="mm", comment="Width parameter")
(calls message_box with message="Width parameter created successfully")
"""
        
        # Create directory for communication files
        # Check both possible locations - within the add-in and in the workspace
        workspace_dir = Path("C:/Users/Joseph/Documents/code/fusion-mcp-server")
        workspace_comm_dir = workspace_dir / "mcp_comm"
        addin_comm_dir = Path(__file__).parent.parent.parent / "mcp_comm"
        
        # Use both directories for communication
        comm_dirs = []
        
        # Add add-in directory 
        addin_comm_dir.mkdir(exist_ok=True)
        comm_dirs.append(addin_comm_dir)
        
        # Add workspace directory if it exists
        if workspace_dir.exists():
            workspace_comm_dir.mkdir(exist_ok=True)
            comm_dirs.append(workspace_comm_dir)
            
        app.log(f"Monitoring communication directories: {[str(d) for d in comm_dirs]}")
            
        # Create ready file
        ready_file_paths = [
            Path(__file__).parent.parent.parent / "mcp_server_ready.txt",
            Path(__file__).parent.parent / "mcp_server_ready.txt",
            addin_comm_dir / "mcp_server_ready.txt",
            workspace_comm_dir / "mcp_server_ready.txt",
            Path.home() / "Desktop" / "mcp_server_ready.txt"
        ]
        
        for ready_file_path in ready_file_paths:
            try:
                with open(ready_file_path, 'w') as f:
                    f.write(f"Fusion 360 MCP Server ready at {time.ctime()}")
                print(f"Created ready file at: {ready_file_path}")
            except:
                print(f"Could not create ready file at: {ready_file_path}")
        
        # Handle file-based communication
        def file_based_communication():
            print("Starting file-based communication handler...")
            
            while server_running:
                # Check for command files in all comm_dirs
                try:
                    for comm_dir in comm_dirs:
                        for cmd_file in comm_dir.glob("command_*.json"):
                            try:
                                print(f"Found command file: {cmd_file}")
                                with open(cmd_file, 'r') as f:
                                    cmd_data = json.load(f)
                                
                                # Process the command
                                cmd_id = cmd_data.get('id', 0)
                                cmd_name = cmd_data.get('command', '')
                                cmd_params = cmd_data.get('params', {})
                                
                                # Create response file in the same directory as the command file
                                response_file = cmd_file.parent / f"response_{cmd_id}.json"
                                
                                # Skip if response already exists
                                if response_file.exists():
                                    continue
                                
                                # Process different commands
                                response_data = {"id": cmd_id, "success": False, "error": "Unknown command"}
                                
                                if cmd_name == "list_resources":
                                    resources = ["active-document-info", "design-structure", "parameters"]
                                    response_data = {"id": cmd_id, "success": True, "resources": resources}
                                
                                elif cmd_name == "get_resource":
                                    resource_name = cmd_params.get("resource_name", "")
                                    if resource_name == "active-document-info":
                                        response_data = {"id": cmd_id, "success": True, "data": get_active_document_info()}
                                    elif resource_name == "design-structure":
                                        response_data = {"id": cmd_id, "success": True, "data": get_design_structure()}
                                    elif resource_name == "parameters":
                                        response_data = {"id": cmd_id, "success": True, "data": get_parameters()}
                                    else:
                                        response_data = {"id": cmd_id, "success": False, "error": f"Unknown resource: {resource_name}"}
                                
                                elif cmd_name == "list_tools":
                                    tools = ["message_box", "create_new_sketch", "create_parameter"]
                                    response_data = {"id": cmd_id, "success": True, "tools": tools}
                                
                                elif cmd_name == "call_tool":
                                    tool_name = cmd_params.get("tool_name", "")
                                    tool_params = cmd_params.get("params", {})
                                    
                                    if tool_name == "message_box":
                                        message = tool_params.get("message", "")
                                        result = message_box(message)
                                        response_data = {"id": cmd_id, "success": True, "result": result}
                                    
                                    elif tool_name == "create_new_sketch":
                                        plane_name = tool_params.get("plane_name", "XY")
                                        result = create_new_sketch(plane_name)
                                        response_data = {"id": cmd_id, "success": True, "result": result}
                                    
                                    elif tool_name == "create_parameter":
                                        name = tool_params.get("name", "")
                                        expression = tool_params.get("expression", "")
                                        unit = tool_params.get("unit", "")
                                        comment = tool_params.get("comment", "")
                                        result = create_parameter(name, expression, unit, comment)
                                        response_data = {"id": cmd_id, "success": True, "result": result}
                                    
                                    else:
                                        response_data = {"id": cmd_id, "success": False, "error": f"Unknown tool: {tool_name}"}
                                
                                elif cmd_name == "list_prompts":
                                    prompts = ["create_sketch_prompt", "parameter_setup_prompt"]
                                    response_data = {"id": cmd_id, "success": True, "prompts": prompts}
                                
                                elif cmd_name == "get_prompt":
                                    prompt_name = cmd_params.get("prompt_name", "")
                                    if prompt_name == "create_sketch_prompt":
                                        response_data = {"id": cmd_id, "success": True, "content": create_sketch_prompt()}
                                    elif prompt_name == "parameter_setup_prompt":
                                        response_data = {"id": cmd_id, "success": True, "content": parameter_setup_prompt()}
                                    else:
                                        response_data = {"id": cmd_id, "success": False, "error": f"Unknown prompt: {prompt_name}"}
                                
                                elif cmd_name == "message_box":
                                    message = cmd_params.get("message", "")
                                    result = message_box(message)
                                    response_data = {"id": cmd_id, "success": True, "result": result}
                                
                                # Write response file
                                with open(response_file, 'w') as f:
                                    json.dump(response_data, f, indent=2)
                                
                                print(f"Created response file: {response_file}")
                                
                                # Delete command file after processing
                                cmd_file.unlink()
                                
                            except Exception as e:
                                print(f"Error processing command file {cmd_file}: {str(e)}")
                                traceback.print_exc()
                                
                                # Create error response
                                try:
                                    with open(cmd_file, 'r') as f:
                                        cmd_data = json.load(f)
                                    cmd_id = cmd_data.get('id', 0)
                                    response_file = cmd_file.parent / f"response_{cmd_id}.json"
                                    
                                    error_response = {
                                        "id": cmd_id,
                                        "success": False,
                                        "error": str(e),
                                        "traceback": traceback.format_exc()
                                    }
                                    
                                    with open(response_file, 'w') as f:
                                        json.dump(error_response, f, indent=2)
                                    
                                    # Delete command file after processing
                                    cmd_file.unlink()
                                except:
                                    pass
                
                except Exception as e:
                    print(f"Error in file-based communication handler: {str(e)}")
                    traceback.print_exc()
                
                # Check for message files
                try:
                    for comm_dir in comm_dirs:
                        message_file = comm_dir / "message_box.txt"
                        if message_file.exists():
                            try:
                                with open(message_file, 'r') as f:
                                    content = f.read().strip()
                                
                                if content.startswith("DISPLAY_MESSAGE:"):
                                    message = content[len("DISPLAY_MESSAGE:"):].strip()
                                    message_box(message)
                                
                                # Rename the file to prevent reprocessing
                                processed_file = message_file.parent / f"message_box_processed_{int(time.time())}.txt"
                                message_file.rename(processed_file)
                                
                            except Exception as e:
                                print(f"Error processing message file: {str(e)}")
                                traceback.print_exc()
                except:
                    pass
                
                # Sleep before checking again
                time.sleep(0.5)
        
        # Start file-based communication in a thread
        comm_thread = threading.Thread(target=file_based_communication)
        comm_thread.daemon = True
        comm_thread.start()
        
        # Run the FastMCP server
        app.log("Starting MCP server using FastMCP")
        app.log("This will allow for both file-based and JSON-RPC communication")
        
        # Start the server in HTTP mode (non-blocking)
        try:
            mcp_port = 3030
            fusion_mcp.run(port=mcp_port)
            app.log(f"MCP server started on port {mcp_port}")
        except Exception as e:
            app.log(f"Error starting MCP server: {str(e)}")
            traceback.print_exc()
            
            # Create an error notification file
            try:
                workspace_dir = Path("C:/Users/Joseph/Documents/code/fusion-mcp-server")
                workspace_comm_dir = workspace_dir / "mcp_comm"
                addin_comm_dir = Path(__file__).parent.parent.parent / "mcp_comm"
                
                # Try both locations
                error_dirs = [addin_comm_dir, workspace_comm_dir]
                
                for error_dir in error_dirs:
                    error_dir.mkdir(exist_ok=True)
                    error_file = error_dir / "mcp_server_error.txt"
                    with open(error_file, 'w') as f:
                        f.write(f"MCP Server Error: {str(e)}\n\n{traceback.format_exc()}")
            except:
                pass
        
        # Keep the thread running
        while server_running:
            time.sleep(1)
            
    except Exception as e:
        app.log(f"Error in MCP server thread: {str(e)}")
        traceback.print_exc()
        
        # Create an error notification file
        try:
            workspace_dir = Path("C:/Users/Joseph/Documents/code/fusion-mcp-server")
            workspace_comm_dir = workspace_dir / "mcp_comm"
            addin_comm_dir = Path(__file__).parent.parent.parent / "mcp_comm"
            
            # Try both locations
            error_dirs = [addin_comm_dir, workspace_comm_dir]
            
            for error_dir in error_dirs:
                error_dir.mkdir(exist_ok=True)
                error_file = error_dir / "mcp_server_error.txt"
                with open(error_file, 'w') as f:
                    f.write(f"MCP Server Error: {str(e)}\n\n{traceback.format_exc()}")
        except:
            pass

# Function to start the server
def start_server():
    global server_thread, server_running
    
    if server_running:
        app.log("MCP server is already running")
        return
    
    # Check if MCP is installed
    if not check_mcp_installed():
        app.log("MCP package is not installed. Please install it with: pip install 'mcp[cli]'")
        ui.messageBox("MCP package is not installed. Please install it with: pip install \"mcp[cli]\"")
        return
    
    # Set server running flag
    server_running = True
    
    # Start server in a separate thread
    server_thread = threading.Thread(target=run_mcp_server)
    server_thread.daemon = True
    server_thread.start()
    
    app.log("MCP server started")

# Function to stop the server
def stop_server():
    global server_running
    
    if not server_running:
        app.log("MCP server is not running")
        return
    
    # Set server running flag to stop the server loop
    server_running = False
    
    # Wait for the thread to finish
    if server_thread and server_thread.is_alive():
        server_thread.join(timeout=2.0)
    
    app.log("MCP server stopped")

# Command event handlers
class MCPServerCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
        
    def notify(self, args):
        try:
            cmd = args.command
            
            # Add a simple button to start/stop the server
            cmd.isExecutedWhenPreEmpted = False
            cmd.isOKButtonVisible = True
            cmd.okButtonText = "Toggle Server"
            
            # Update information about server status in the dialog's title
            if server_running:
                cmd.dialogTitle = "MCP Server (Running)"
            else:
                cmd.dialogTitle = "MCP Server (Stopped)"
                
            # Create a read-only text box to show server status
            statusInput = cmd.commandInputs.addTextBoxCommandInput('serverStatus', 'Server Status', 
                                                                 "The MCP server is " + 
                                                                 ("running" if server_running else "not running"), 
                                                                 3, True)
            
            # Connect to the execute event
            onExecute = MCPServerCommandExecuteHandler()
            cmd.execute.add(onExecute)
            futil.add_handler(cmd.execute, onExecute)
            
            # Connect to the destroy event
            onDestroy = MCPServerCommandDestroyHandler()
            cmd.destroy.add(onDestroy)
            futil.add_handler(cmd.destroy, onDestroy)
            
        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

class MCPServerCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
        
    def notify(self, args):
        try:
            # Toggle server state
            global server_running
            
            if server_running:
                stop_server()
                ui.messageBox('MCP Server stopped')
            else:
                start_server()
                if server_running:
                    ui.messageBox('MCP Server started')
                
        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

class MCPServerCommandDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
        
    def notify(self, args):
        try:
            # Cleanup if needed
            pass
        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

# Create the command definition
def start():
    """Called when the add-in is starting."""
    try:
        # Create the command definition
        cmd_def = ui.commandDefinitions.itemById('MCPServerCommand')
        if not cmd_def:
            cmd_def = ui.commandDefinitions.addButtonDefinition(
                'MCPServerCommand',
                'MCP Server',
                'Start or stop the Model Context Protocol server',
                './resources'
            )
        
        # Connect to command created event
        onCommandCreated = MCPServerCommandCreatedHandler()
        cmd_def.commandCreated.add(onCommandCreated)
        futil.add_handler(cmd_def.commandCreated, onCommandCreated)
        
        # Get the ADD-INS panel in the model workspace
        workspace = ui.workspaces.itemById('FusionSolidEnvironment')
        panel = workspace.toolbarPanels.itemById('SolidScriptsAddinsPanel')
        
        # Add the button to the panel
        control = panel.controls.itemById('MCPServerCommand')
        if not control:
            panel.controls.addCommand(cmd_def)
        
        # Start the server automatically
        app.log("Starting MCP server automatically")
        start_server()
        
    except:
        ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

def stop():
    """Called when the add-in is stopping."""
    try:
        # Stop the server if it's running
        if server_running:
            stop_server()
        
        # Remove the command from the toolbar
        workspace = ui.workspaces.itemById('FusionSolidEnvironment')
        panel = workspace.toolbarPanels.itemById('SolidScriptsAddinsPanel')
        command_control = panel.controls.itemById('MCPServerCommand')
        if command_control:
            command_control.deleteMe()
        
        # Delete the command definition
        command_definition = ui.commandDefinitions.itemById('MCPServerCommand')
        if command_definition:
            command_definition.deleteMe()
            
    except:
        ui.messageBox('Failed:\n{}'.format(traceback.format_exc())) 