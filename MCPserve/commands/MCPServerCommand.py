#!/usr/bin/env python3

import adsk.core
import adsk.fusion
import os
import sys
import traceback
import threading
import time
import json
import asyncio
from pathlib import Path

from ..lib import fusionAddInUtils as futil

# Global variables
app = adsk.core.Application.get()
ui = app.userInterface
server_thread = None
server_running = False

# Initialize the global handlers list
handlers = []

# Function to check if MCP package is installed
def check_mcp_installed():
    missing_packages = []
    
    try:
        import mcp
        print(f"Found MCP package at: {mcp.__file__}")
    except ImportError as e:
        print(f"Error importing MCP package: {str(e)}")
        missing_packages.append("mcp[cli]")
    
    try:
        import uvicorn
        print(f"Found uvicorn package at: {uvicorn.__file__}")
    except ImportError as e:
        print(f"Error importing uvicorn package: {str(e)}")
        missing_packages.append("uvicorn")
    
    if missing_packages:
        print(f"Missing required packages: {', '.join(missing_packages)}")
        return False
    
    return True

# Function to run MCP server
def run_mcp_server():
    try:
        # Import required MCP modules
        import mcp
        from mcp.server.fastmcp import FastMCP
        import uvicorn
        import threading
        
        # Create workspace path and diagnostic log
        workspace_path = "C:/Users/Joseph/Documents/code/fusion-mcp-server"
        workspace_comm_dir = os.path.join(workspace_path, "mcp_comm")
        os.makedirs(workspace_comm_dir, exist_ok=True)
        
        # Write diagnostic info without relying on __version__
        diagnostic_log = os.path.join(workspace_comm_dir, "mcp_server_diagnostics.log")
        with open(diagnostic_log, "w") as f:
            f.write(f"MCP Server Diagnostics - {time.ctime()}\n\n")
            f.write(f"Server URL: http://127.0.0.1:3000/sse\n")
            f.write(f"Workspace directory: {workspace_path}\n")
            f.write(f"Communication directory: {workspace_comm_dir}\n\n")
            f.write(f"Python version: {sys.version}\n\n")
            f.write(f"Registered Resources:\n  (Method available_resources() not available in this MCP SDK version)\n\n")
            f.write(f"Registered Tools:\n  (Method available_tools() not available in this MCP SDK version)\n\n")
            f.write(f"Registered Prompts:\n  (Method available_prompts() not available in this MCP SDK version)\n\n")
            f.write(f"Environment:\n  Python version: {sys.version}\n  MCP SDK available: True\n\n")
        
        print("Creating FastMCP server instance...")
        # Create the MCP server
        fusion_mcp = FastMCP("Fusion 360 MCP Server")
        
        # Write more diagnostics about the FastMCP object
        with open(diagnostic_log, "a") as f:
            f.write(f"FastMCP Object Attributes:\n")
            for attr in dir(fusion_mcp):
                if not attr.startswith('_'):
                    f.write(f"  - {attr}\n")
            f.write("\n")
        
        print("Registering resources...")
        # Define resources - Note: All resource URIs must have a scheme
        @fusion_mcp.resource("fusion://active-document-info")
        def get_active_document_info():
            """Get information about the active document in Fusion 360."""
            try:
                doc = app.activeDocument
                if doc:
                    return {
                        "name": doc.name,
                        "path": doc.dataFile.name if doc.dataFile else "Unsaved",
                        "type": str(doc.documentType)
                    }
                else:
                    return {"error": "No active document"}
            except Exception as e:
                return {"error": str(e) + "\n" + traceback.format_exc()}
        
        @fusion_mcp.resource("fusion://design-structure")
        def get_design_structure():
            """Get the structure of the active design in Fusion 360."""
            try:
                doc = app.activeDocument
                if not doc:
                    return {"error": "No active document"}
                
                if str(doc.documentType) != "FusionDesignDocumentType":
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
            except Exception as e:
                return {"error": str(e) + "\n" + traceback.format_exc()}
        
        @fusion_mcp.resource("fusion://parameters")
        def get_parameters():
            """Get the parameters of the active design in Fusion 360."""
            try:
                doc = app.activeDocument
                if not doc:
                    return {"error": "No active document"}
                
                if str(doc.documentType) != "FusionDesignDocumentType":
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
            except Exception as e:
                return {"error": str(e) + "\n" + traceback.format_exc()}
        
        print("Registering tools...")
        # Define tools
        @fusion_mcp.tool()
        def message_box(message: str) -> str:
            """Display a message box in Fusion 360."""
            try:
                ui.messageBox(message)
                return "Message displayed successfully"
            except Exception as e:
                return f"Error displaying message: {str(e)}"
        
        @fusion_mcp.tool()
        def create_new_sketch(plane_name: str) -> str:
            """Create a new sketch on the specified plane."""
            try:
                doc = app.activeDocument
                if not doc:
                    return "No active document"
                
                if str(doc.documentType) != "FusionDesignDocumentType":
                    return "Not a Fusion design document"
                
                design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
                if not design:
                    return "No design in document"
                
                root_comp = design.rootComponent
                
                # Find the plane
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
                    construction_planes = root_comp.constructionPlanes
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
                
                return f"Sketch created successfully: {sketch.name}"
            except Exception as e:
                return f"Error creating sketch: {str(e)}"
        
        @fusion_mcp.tool()
        def create_parameter(name: str, expression: str, unit: str, comment: str = "") -> str:
            """Create a new parameter in the active design."""
            try:
                doc = app.activeDocument
                if not doc:
                    return "No active document"
                
                if str(doc.documentType) != "FusionDesignDocumentType":
                    return "Not a Fusion design document"
                
                design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
                if not design:
                    return "No design in document"
                
                # Create the parameter
                param = design.userParameters.add(name, adsk.core.ValueInput.createByString(expression), unit, comment)
                
                return f"Parameter created successfully: {param.name} = {param.expression}"
            except Exception as e:
                return f"Error creating parameter: {str(e)}"
        
        print("Registering prompts...")
        # Define prompts
        @fusion_mcp.prompt()
        def create_sketch_prompt(description: str) -> dict:
            """Create a prompt for creating a sketch based on a description."""
            return {
                "messages": [
                    {
                        "role": "system",
                        "content": """You are an expert in Fusion 360 CAD modeling. Your task is to help the user create sketches based on their descriptions.
                        
Be very specific about what planes to use and what sketch entities to create.
"""
                    },
                    {
                        "role": "user",
                        "content": f"I want to create a sketch with these requirements: {description}\n\nPlease provide step-by-step instructions for creating this sketch in Fusion 360."
                    }
                ]
            }
        
        @fusion_mcp.prompt()
        def parameter_setup_prompt(description: str) -> dict:
            """Create a prompt for setting up parameters based on a description."""
            return {
                "messages": [
                    {
                        "role": "system",
                        "content": """You are an expert in Fusion 360 parametric design. Your task is to help the user set up parameters for their design.

Suggest appropriate parameters, their values, units, and purposes based on the user's description.
"""
                    },
                    {
                        "role": "user",
                        "content": f"I want to set up parameters for: {description}\n\nWhat parameters should I create, and what values, units, and comments should they have?"
                    }
                ]
            }
        
        # Set up file-based communication
        print("Setting up file-based communication...")
        
        # Paths for the add-in and workspace directories
        addon_path = os.path.dirname(os.path.dirname(__file__))
        addon_comm_dir = os.path.join(addon_path, "mcp_comm")
        os.makedirs(addon_comm_dir, exist_ok=True)
        
        # Workspace path (the fusion-mcp-server repository)
        workspace_path = "C:/Users/Joseph/Documents/code/fusion-mcp-server"
        workspace_comm_dir = Path(workspace_path) / "mcp_comm"
        if os.path.exists(workspace_path):
            os.makedirs(str(workspace_comm_dir), exist_ok=True)
        
        # Create a list of communication directories to monitor
        comm_dirs = [
            addon_comm_dir,
            str(workspace_comm_dir)
        ]
        
        # Create desktop path for ready file
        ready_file_desktop = os.path.expanduser("~/Desktop/mcp_server_ready.txt")
        
        # Create server info file
        server_info_file = os.path.join(workspace_comm_dir, "mcp_server_info.txt")
        with open(server_info_file, "w") as f:
            f.write(f"MCP Server started at {time.ctime()}\n")
            f.write(f"Python version: {sys.version}\n")
        
        # Create server status file with JSON structure
        server_status_file = os.path.join(workspace_comm_dir, "server_status.json")
        with open(server_status_file, "w") as f:
            status_data = {
                "status": "running",
                "started_at": time.ctime(),
                "server_url": "http://127.0.0.1:3000/sse",
                "fusion_version": app.version,
                "available_resources": [
                    "fusion://active-document-info",
                    "fusion://design-structure",
                    "fusion://parameters"
                ],
                "available_tools": [
                    "message_box",
                    "create_new_sketch",
                    "create_parameter"
                ],
                "available_prompts": [
                    "create_sketch_prompt",
                    "parameter_setup_prompt"
                ]
            }
            json.dump(status_data, f, indent=2)
        
        # Create all ready file paths
        ready_files = [
            ready_file_desktop,
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "mcp_server_ready.txt"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mcp_server_ready.txt"),
            os.path.join(workspace_path, "mcp_server_ready.txt"),
            str(workspace_comm_dir / "mcp_server_ready.txt")
        ]
        
        # Create all ready files
        for ready_file in ready_files:
            try:
                os.makedirs(os.path.dirname(ready_file), exist_ok=True)
                with open(ready_file, "w") as f:
                    f.write(f"MCP Server Ready - {time.ctime()}")
                print(f"Created ready file: {ready_file}")
            except Exception as e:
                print(f"Error creating ready file at {ready_file}: {str(e)}")
        
        # Run the FastMCP server
        print("Starting MCP server using FastMCP with uvicorn")
        
        # Get the Starlette app from the sse_app method
        sse_app = fusion_mcp.sse_app()
        
        # Port and host for the server
        host = "127.0.0.1"
        port = 3000  # Default port for SSE
        
        # Create a Config instance for uvicorn
        config = uvicorn.Config(
            sse_app,
            host=host,
            port=port,
            log_level="info"
        )
        
        # Create server instance
        server = uvicorn.Server(config)
        
        # Run server in a separate thread
        def uvicorn_thread():
            try:
                # Create initialization log
                init_log_file = os.path.join(workspace_comm_dir, "mcp_server_init.log")
                with open(init_log_file, "w") as f:
                    f.write(f"Starting uvicorn server at {time.ctime()}\n")
                    f.write(f"Host: {host}, Port: {port}\n")
                
                # Run the server
                server.run()
            except Exception as e:
                error_msg = f"Error in uvicorn server: {str(e)}"
                print(error_msg)
                
                # Write error to file
                error_file = os.path.join(workspace_comm_dir, "mcp_server_uvicorn_error.txt")
                with open(error_file, "w") as f:
                    f.write(error_msg + "\n")
                    f.write(traceback.format_exc())
        
        # Start the server in a thread
        uvicorn_thread = threading.Thread(target=uvicorn_thread)
        uvicorn_thread.daemon = True
        uvicorn_thread.start()
        
        print(f"MCP server started at http://{host}:{port}/sse")
        
        # Monitor for command files in a separate thread
        def file_monitor_thread():
            try:
                print("Starting file monitor thread...")
                
                # Create a file to track thread status
                monitor_file = os.path.join(workspace_comm_dir, "file_monitor_status.txt")
                with open(monitor_file, "w") as f:
                    f.write(f"File monitor thread started at {time.ctime()}\n")
                
                while server_running:
                    # Check each communication directory for command files
                    for comm_dir in comm_dirs:
                        try:
                            # Create directory if it doesn't exist
                            os.makedirs(comm_dir, exist_ok=True)
                            
                            # Check for message box files
                            message_file = os.path.join(comm_dir, "message_box.txt")
                            if os.path.exists(message_file):
                                try:
                                    with open(message_file, "r") as f:
                                        message = f.read().strip()
                                    
                                    # Display the message
                                    print(f"Displaying message box: {message}")
                                    ui.messageBox(message)
                                    
                                    # Rename the file to avoid processing it again
                                    processed_file = os.path.join(comm_dir, f"processed_message_{int(time.time())}.txt")
                                    os.rename(message_file, processed_file)
                                except Exception as e:
                                    print(f"Error processing message file {message_file}: {str(e)}")
                            
                            # Check for command files
                            for file in os.listdir(comm_dir):
                                if file.startswith("command_") and file.endswith(".json"):
                                    command_file = os.path.join(comm_dir, file)
                                    try:
                                        # Extract the command ID from the filename
                                        command_id = file.split("_")[1].split(".")[0]
                                        
                                        # Check if we've already processed this command
                                        processed_file = os.path.join(comm_dir, f"processed_command_{command_id}.json")
                                        response_file = os.path.join(comm_dir, f"response_{command_id}.json")
                                        
                                        if os.path.exists(processed_file) or os.path.exists(response_file):
                                            continue  # Skip if already processed
                                        
                                        print(f"Processing command file: {command_file}")
                                        
                                        # Read command data
                                        try:
                                            with open(command_file, "r") as f:
                                                command_data = json.load(f)
                                            
                                            command = command_data.get("command")
                                            params = command_data.get("params", {})
                                            
                                            print(f"Processing command {command_id}: {command} with params {params}")
                                            
                                            result = None
                                            
                                            # Handle the command
                                            if command == "list_resources":
                                                # Get available resources
                                                resources = [
                                                    "fusion://active-document-info",
                                                    "fusion://design-structure",
                                                    "fusion://parameters"
                                                ]
                                                result = resources
                                            elif command == "list_tools":
                                                # Get available tools
                                                tools = [
                                                    {"name": "message_box", "description": "Display a message box in Fusion 360"},
                                                    {"name": "create_new_sketch", "description": "Create a new sketch on the specified plane"},
                                                    {"name": "create_parameter", "description": "Create a new parameter in the active design"}
                                                ]
                                                result = tools
                                            elif command == "list_prompts":
                                                # Get available prompts
                                                prompts = [
                                                    {"name": "create_sketch_prompt", "description": "Create a prompt for creating a sketch based on a description"},
                                                    {"name": "parameter_setup_prompt", "description": "Create a prompt for setting up parameters based on a description"}
                                                ]
                                                result = prompts
                                            elif command == "message_box":
                                                # Display a message box
                                                message = params.get("message", "")
                                                ui.messageBox(message)
                                                result = "Message displayed successfully"
                                            elif command == "create_new_sketch":
                                                # Create a new sketch
                                                result = create_new_sketch(params.get("plane_name", "XY"))
                                            elif command == "create_parameter":
                                                # Create a new parameter
                                                result = create_parameter(
                                                    params.get("name", f"Param_{int(time.time()) % 10000}"),
                                                    params.get("expression", "10"),
                                                    params.get("unit", "mm"),
                                                    params.get("comment", "")
                                                )
                                            else:
                                                result = f"Unknown command: {command}"
                                            
                                            # Write the response
                                            with open(response_file, "w") as f:
                                                json.dump({"result": result}, f, indent=2)
                                            
                                            # Rename the command file to avoid processing it again
                                            os.rename(command_file, processed_file)
                                        except json.JSONDecodeError as e:
                                            # Handle JSON parsing error
                                            print(f"Error parsing JSON in {command_file}: {str(e)}")
                                            with open(response_file, "w") as f:
                                                json.dump({"error": f"Invalid JSON format: {str(e)}"}, f, indent=2)
                                    except Exception as e:
                                        print(f"Error processing command file {command_file}: {str(e)}")
                                        traceback.print_exc()
                                        
                                        # Try to create an error response anyway
                                        try:
                                            with open(os.path.join(comm_dir, f"response_{command_id}.json"), "w") as f:
                                                json.dump({"error": str(e)}, f, indent=2)
                                        except Exception:
                                            pass
                        except Exception as e:
                            print(f"Error processing directory {comm_dir}: {str(e)}")
                            error_file = os.path.join(workspace_comm_dir, "error.txt")
                            with open(error_file, "w") as f:
                                f.write(f"Error in file monitor for directory {comm_dir}: {str(e)}\n\n{traceback.format_exc()}")
                    
                    # Sleep to avoid high CPU usage
                    time.sleep(0.5)
            except Exception as e:
                print(f"Error in file monitor thread: {str(e)}")
                error_file = os.path.join(workspace_comm_dir, "error.txt")
                with open(error_file, "w") as f:
                    f.write(f"File Monitor Error: {str(e)}\n\n{traceback.format_exc()}")
        
        # Start the file monitor thread
        file_monitor = threading.Thread(target=file_monitor_thread)
        file_monitor.daemon = True
        file_monitor.start()
        
        # Keep thread running
        while server_running:
            time.sleep(1)
            
        # Shutdown the server
        print("Shutting down server...")
        server.should_exit = True
        
        return True
        
    except Exception as e:
        print(f"Error in MCP server: {str(e)}")
        
        # Create error file
        workspace_path = "C:/Users/Joseph/Documents/code/fusion-mcp-server"
        if os.path.exists(workspace_path):
            workspace_comm_dir = os.path.join(workspace_path, "mcp_comm")
            os.makedirs(workspace_comm_dir, exist_ok=True)
            error_file = os.path.join(workspace_comm_dir, "mcp_server_error.txt")
            with open(error_file, "w") as f:
                f.write(f"MCP Server Error: {str(e)}\n\n{traceback.format_exc()}")
        
        return False

# Function to start the server
def start_server():
    global server_thread
    global server_running
    
    print("Starting MCP server...")
    
    # Create workspace comm directory if it doesn't exist
    workspace_path = "C:/Users/Joseph/Documents/code/fusion-mcp-server"
    workspace_comm_dir = os.path.join(workspace_path, "mcp_comm")
    if os.path.exists(workspace_path):
        os.makedirs(workspace_comm_dir, exist_ok=True)
        # Create a log file
        log_file = os.path.join(workspace_comm_dir, "mcp_server_log.txt")
        with open(log_file, "w") as f:
            f.write(f"MCP Server starting at {time.ctime()}\n")
    
    # Check if MCP is installed
    if not check_mcp_installed():
        print("Required packages not installed. Cannot start server.")
        ui.messageBox("Required packages are not installed. Please install them with:\npip install \"mcp[cli]\" uvicorn")
        return False
    
    # Check if server is already running
    if server_running and server_thread and server_thread.is_alive():
        print("MCP server is already running")
        return True
    
    # Reset server state
    server_running = True
    
    # Start server in a separate thread
    def server_thread_func():
        try:
            success = run_mcp_server()
            if not success:
                print("Failed to start MCP server")
                server_running = False
                ui.messageBox("Failed to start MCP server. See error log for details.")
        except Exception as e:
            print(f"Error in server thread: {str(e)}")
            server_running = False
            error_file = os.path.join(workspace_comm_dir, "mcp_server_error.txt")
            with open(error_file, "w") as f:
                f.write(f"MCP Server Thread Error: {str(e)}\n\n{traceback.format_exc()}")
    
    server_thread = threading.Thread(target=server_thread_func)
    server_thread.daemon = True
    server_thread.start()
    
    print("MCP server thread started")
    
    # Wait a moment for the server to initialize
    time.sleep(1)
    
    # Check if the thread is still alive
    if not server_thread.is_alive():
        print("MCP server thread stopped unexpectedly")
        server_running = False
        return False
    
    print("MCP server started successfully")
    return True

# Function to stop the server
def stop_server():
    global server_running
    
    if not server_running:
        print("MCP server is not running")
        return
    
    # Set server running flag to stop the server loop
    server_running = False
    
    # Wait for the thread to finish
    if server_thread and server_thread.is_alive():
        server_thread.join(timeout=2.0)
    
    print("MCP server stopped")

# Command event handlers
class MCPServerCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    
    def notify(self, args):
        try:
            # Get command inputs
            cmd = args.command
            inputs = cmd.commandInputs
            
            # Add information text
            info_input = inputs.addTextBoxCommandInput('infoInput', '', 
                'Click OK to start the MCP Server.\n\n' +
                'This will enable communication between Fusion 360 and MCP clients.\n\n' +
                'Current server status: ' + ('Running' if server_running else 'Not Running'), 
                4, True)
            
            # Events
            onExecute = MCPServerCommandExecuteHandler()
            cmd.execute.add(onExecute)
            handlers.append(onExecute)
            
            onDestroy = MCPServerCommandDestroyHandler()
            cmd.destroy.add(onDestroy)
            handlers.append(onDestroy)
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

class MCPServerCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    
    def notify(self, args):
        try:
            # Start the server
            success = start_server()
            
            if success:
                workspace_path = "C:/Users/Joseph/Documents/code/fusion-mcp-server"
                workspace_comm_dir = os.path.join(workspace_path, "mcp_comm")
                
                # Create a startup log file
                startup_log_file = os.path.join(workspace_comm_dir, "mcp_server_startup_log.txt")
                with open(startup_log_file, "w") as f:
                    f.write(f"MCP Server started successfully at {time.ctime()}\n")
                    f.write(f"Server URL: http://127.0.0.1:3000/sse\n")
                    f.write(f"Communication directory: {workspace_comm_dir}\n")
                
                ui.messageBox("MCP Server started successfully!\n\nServer is running at http://127.0.0.1:3000/sse\n\nReady for client connections.")
            else:
                workspace_path = "C:/Users/Joseph/Documents/code/fusion-mcp-server"
                workspace_comm_dir = os.path.join(workspace_path, "mcp_comm")
                
                # Check for error file
                error_file = os.path.join(workspace_comm_dir, "mcp_server_error.txt")
                error_message = "Unknown error. See error log for details."
                
                if os.path.exists(error_file):
                    try:
                        with open(error_file, "r") as f:
                            error_message = f.read()
                    except:
                        pass
                
                ui.messageBox(f"Failed to start MCP Server. Error: {error_message}")
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

class MCPServerCommandDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    
    def notify(self, args):
        try:
            # Clean up as needed
            pass
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

# Function to stop server on add-in stop
def stop_server_on_stop(context):
    try:
        global server_running
        
        if server_running:
            print("Stopping MCP server...")
            server_running = False
            
            # Create a shutdown log file
            workspace_path = "C:/Users/Joseph/Documents/code/fusion-mcp-server"
            workspace_comm_dir = os.path.join(workspace_path, "mcp_comm")
            os.makedirs(workspace_comm_dir, exist_ok=True)
            
            shutdown_log_file = os.path.join(workspace_comm_dir, "mcp_server_shutdown_log.txt")
            with open(shutdown_log_file, "w") as f:
                f.write(f"MCP Server stopped at {time.ctime()}\n")
            
            # Wait for the thread to finish
            if server_thread and server_thread.is_alive():
                server_thread.join(timeout=2.0)
            
            print("MCP server stopped")
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

# Function to create the UI elements
def create_ui():
    try:
        # Get the command definitions
        command_definitions = ui.commandDefinitions
        
        # Create a command definition for the MCP server command
        mcp_server_cmd_def = command_definitions.itemById('MCPServerCommand')
        if not mcp_server_cmd_def:
            mcp_server_cmd_def = command_definitions.addButtonDefinition('MCPServerCommand', 'MCP Server', 'Start the MCP Server for Fusion 360')
        
        # Connect to the command created event
        on_command_created = MCPServerCommandCreatedHandler()
        mcp_server_cmd_def.commandCreated.add(on_command_created)
        handlers.append(on_command_created)
        
        # Add to the add-ins panel
        add_ins_panel = ui.allToolbarPanels.itemById('SolidScriptsAddinsPanel')
        control = add_ins_panel.controls.itemById('MCPServerCommand')
        if not control:
            add_ins_panel.controls.addCommand(mcp_server_cmd_def)
        
        print("MCP Server command added to UI")
    except:
        if ui:
            ui.messageBox('Failed to create UI:\n{}'.format(traceback.format_exc()))

# Define the required start() and stop() functions for the add-in system
def start():
    """Called when the add-in is started."""
    try:
        create_ui()
    except:
        if ui:
            ui.messageBox('Failed to initialize add-in:\n{}'.format(traceback.format_exc()))

def stop():
    """Called when the add-in is stopped."""
    try:
        # Stop the server
        stop_server_on_stop(None)
        
        # Clean up UI
        command_definitions = ui.commandDefinitions
        mcp_server_cmd_def = command_definitions.itemById('MCPServerCommand')
        if mcp_server_cmd_def:
            mcp_server_cmd_def.deleteMe()
        
        # Clean up any panels
        add_ins_panel = ui.allToolbarPanels.itemById('SolidScriptsAddinsPanel')
        control = add_ins_panel.controls.itemById('MCPServerCommand')
        if control:
            control.deleteMe()
            
        print("MCP Server add-in stopped")
    except:
        if ui:
            ui.messageBox('Failed to clean up add-in:\n{}'.format(traceback.format_exc()))

# Main entry point
def run(context):
    try:
        create_ui()
    except:
        if ui:
            ui.messageBox('Failed to run:\n{}'.format(traceback.format_exc())) 