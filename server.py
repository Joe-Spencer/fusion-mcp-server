"""
Fusion 360 MCP Server

This server provides Model Context Protocol (MCP) capabilities for Autodesk Fusion 360,
allowing AI assistants to access Fusion 360 resources and tools.
"""

import traceback
import adsk.core
import adsk.fusion
from mcp.server.fastmcp import FastMCP
import json
import os

# Initialize Fusion 360 application
app = adsk.core.Application.get()
ui = app.userInterface

# Create MCP server instance
mcp = FastMCP("Fusion 360 MCP")

# ------ Resources ------

@mcp.resource("active-document-info")
def get_active_document_info() -> str:
    """Get information about the active document"""
    try:
        doc = app.activeDocument
        if doc:
            return json.dumps({
                "name": doc.name,
                "path": doc.dataFile.fullPath if doc.dataFile else "Unsaved",
                "type": doc.documentType
            })
        else:
            return json.dumps({"error": "No active document"})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.resource("design-structure")
def get_design_structure() -> str:
    """Get the structure of the active design"""
    try:
        product = app.activeProduct
        if not product or product.productType != 'DesignProductType':
            return json.dumps({"error": "No active design"})
        
        design = adsk.fusion.Design.cast(product)
        if not design:
            return json.dumps({"error": "Failed to cast to Design"})
        
        rootComp = design.rootComponent
        
        def serialize_component(comp):
            result = {
                "name": comp.name,
                "occurrences": [],
                "bodies": [],
                "sketches": [],
                "features": []
            }
            
            # Add occurrences
            for occ in comp.occurrences:
                result["occurrences"].append({
                    "name": occ.name,
                    "component": occ.component.name
                })
            
            # Add bodies
            for body in comp.bRepBodies:
                result["bodies"].append({
                    "name": body.name,
                    "isValid": body.isValid,
                    "isSolid": body.isSolid
                })
            
            # Add sketches
            for sketch in comp.sketches:
                sketch_data = {
                    "name": sketch.name,
                    "sketchCurves": sketch.sketchCurves.count,
                    "sketchPoints": sketch.sketchPoints.count
                }
                result["sketches"].append(sketch_data)
            
            # Add features
            for feature in comp.features:
                result["features"].append({
                    "name": feature.name,
                    "type": feature.classType()
                })
            
            return result
        
        structure = serialize_component(rootComp)
        return json.dumps(structure)
    except Exception as e:
        return json.dumps({"error": str(e), "traceback": traceback.format_exc()})

@mcp.resource("parameters")
def get_parameters() -> str:
    """Get the user parameters defined in the active document"""
    try:
        product = app.activeProduct
        if not product or product.productType != 'DesignProductType':
            return json.dumps({"error": "No active design"})
        
        design = adsk.fusion.Design.cast(product)
        if not design:
            return json.dumps({"error": "Failed to cast to Design"})
        
        all_params = []
        for param in design.userParameters:
            all_params.append({
                "name": param.name,
                "value": param.value,
                "unit": param.unit,
                "expression": param.expression,
                "comment": param.comment
            })
        
        return json.dumps(all_params)
    except Exception as e:
        return json.dumps({"error": str(e)})

# ------ Tools ------

@mcp.tool()
def message_box(message: str) -> str:
    """Display a message box in Fusion 360"""
    try:
        ui.messageBox(message)
        return json.dumps({"success": True})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def create_new_sketch(plane_name: str = "XY") -> str:
    """Create a new sketch on the specified plane"""
    try:
        product = app.activeProduct
        if not product or product.productType != 'DesignProductType':
            return json.dumps({"error": "No active design"})
        
        design = adsk.fusion.Design.cast(product)
        if not design:
            return json.dumps({"error": "Failed to cast to Design"})
        
        rootComp = design.rootComponent
        
        # Get construction plane
        xyPlane = None
        if plane_name == "XY":
            xyPlane = rootComp.xYConstructionPlane
        elif plane_name == "XZ":
            xyPlane = rootComp.xZConstructionPlane
        elif plane_name == "YZ":
            xyPlane = rootComp.yZConstructionPlane
        else:
            return json.dumps({"error": f"Unknown plane: {plane_name}"})
        
        # Create sketch
        sketches = rootComp.sketches
        sketch = sketches.add(xyPlane)
        
        return json.dumps({
            "success": True,
            "sketch_name": sketch.name
        })
    except Exception as e:
        return json.dumps({"error": str(e), "traceback": traceback.format_exc()})

@mcp.tool()
def create_parameter(name: str, expression: str, unit: str = "", comment: str = "") -> str:
    """Create a new user parameter"""
    try:
        product = app.activeProduct
        if not product or product.productType != 'DesignProductType':
            return json.dumps({"error": "No active design"})
        
        design = adsk.fusion.Design.cast(product)
        if not design:
            return json.dumps({"error": "Failed to cast to Design"})
        
        # Check if parameter already exists
        params = design.userParameters
        for param in params:
            if param.name == name:
                return json.dumps({"error": f"Parameter '{name}' already exists"})
        
        # Create parameter
        new_param = params.add(name, adsk.core.ValueInput.createByString(expression), unit, comment)
        
        return json.dumps({
            "success": True,
            "name": new_param.name,
            "value": new_param.value,
            "unit": new_param.unit
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

# ------ Prompts ------

@mcp.prompt()
def create_sketch_prompt() -> str:
    """Create a prompt for setting up a new sketch"""
    return """
You are helping me create a new sketch in Fusion 360.
Please suggest what plane I should create the sketch on.
Available planes are XY, XZ, and YZ.
After creating the sketch, what type of geometry would you like to add?
"""

@mcp.prompt()
def parameter_setup_prompt() -> str:
    """Create a prompt for setting up new parameters"""
    return """
You are helping me set up parameters for my design in Fusion 360.
Please suggest what parameters I should create for this design.
For each parameter, provide:
1. Name
2. Expression (value with units)
3. Optional comment explaining the purpose
"""

# Main run function
def run(_context=None):
    """Main function to run the MCP server"""
    try:
        ui.messageBox("Starting Fusion 360 MCP Server")
        
        # In a real implementation, you would need to run this in a way
        # that doesn't block the Fusion 360 UI
        # For demonstration purposes, this is simplified
        mcp.run()
        
        return True
    except Exception as e:
        ui.messageBox(f'Failed to start MCP server:\n{traceback.format_exc()}')
        return False

# If run directly (not as a Fusion add-in)
if __name__ == "__main__":
    run() 