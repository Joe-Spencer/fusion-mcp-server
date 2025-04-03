#!/usr/bin/env python3

"""
MCP Client for Fusion 360

This client connects to the Fusion 360 MCP server and provides
a simple interface for testing the server functionality using
stdio-based communication.
"""

import os
import sys
import json
import argparse
import time
import subprocess
import traceback
from pathlib import Path

# Print debugging information
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Python path: {sys.path}")

# Try to import MCP package
try:
    import mcp
    has_mcp = True
    print(f"MCP package found at: {mcp.__file__}")
except ImportError:
    has_mcp = False
    print("MCP package not installed. Will use file-based communication instead.")

# Define the communication directory locations
FUSION_ADDIN_PATH = Path("C:/Users/Joseph/AppData/Roaming/Autodesk/Autodesk Fusion 360/API/AddIns")
FUSION_MCP_COMM_DIR = FUSION_ADDIN_PATH / "MCPserve" / "mcp_comm"
LOCAL_MCP_COMM_DIR = Path(__file__).parent / "mcp_comm"

# Directory for communication files
COMM_DIR = FUSION_MCP_COMM_DIR if FUSION_MCP_COMM_DIR.exists() else LOCAL_MCP_COMM_DIR
COMM_DIR.mkdir(exist_ok=True)

print(f"Using communication directory: {COMM_DIR}")

def create_command_file(command, params=None):
    """Create a command file that Fusion 360 can read."""
    command_id = int(time.time())
    command_file = COMM_DIR / f"command_{command_id}.json"
    
    data = {
        "command": command,
        "params": params or {},
        "timestamp": time.time(),
        "id": command_id
    }
    
    with open(command_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Created command file: {command_file}")
    return command_id, command_file

def wait_for_response(command_id, timeout=10):
    """Wait for a response file from Fusion 360."""
    response_file = COMM_DIR / f"response_{command_id}.json"
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        if response_file.exists():
            try:
                with open(response_file, 'r') as f:
                    response = json.load(f)
                print(f"Got response: {response}")
                return response
            except Exception as e:
                print(f"Error reading response file: {e}")
                return None
        
        time.sleep(0.1)
    
    print(f"Timeout waiting for response to command {command_id}")
    return None

def run_command(command, params=None, timeout=10):
    """Run a command through file-based communication."""
    command_id, command_file = create_command_file(command, params)
    return wait_for_response(command_id, timeout)

def test_resources():
    """Test the resources provided by the server using file-based communication."""
    print("\nTesting resources...")
    
    # List resources
    resource_list = run_command("list_resources")
    if resource_list and "resources" in resource_list:
        print(f"Available resources: {resource_list['resources']}")
        
        # Test specific resources
        for resource_name in ["active-document-info", "design-structure", "parameters"]:
            print(f"Requesting resource: {resource_name}")
            result = run_command("get_resource", {"resource_name": resource_name})
            
            if result and "success" in result and result["success"]:
                print(f"✓ Resource '{resource_name}' available")
                
                # Print some details about the result
                if "data" in result:
                    data = result["data"]
                    if isinstance(data, dict):
                        if len(data) > 0:
                            print(f"  Keys: {', '.join(list(data.keys())[:5])}{' ...' if len(data.keys()) > 5 else ''}")
                        else:
                            print("  (Empty dictionary returned)")
                    elif isinstance(data, list):
                        if len(data) > 0:
                            print(f"  List with {len(data)} items")
                        else:
                            print("  (Empty list returned)")
                    else:
                        print(f"  Data: {str(data)[:100]}{' ...' if len(str(data)) > 100 else ''}")
            else:
                print(f"✗ Resource '{resource_name}' not available")
    else:
        print("Failed to list resources")

def test_tools():
    """Test the tools provided by the server using file-based communication."""
    print("\nTesting tools...")
    
    # List tools
    tool_list = run_command("list_tools")
    if tool_list and "tools" in tool_list:
        print(f"Available tools: {tool_list['tools']}")
        
        # Test message_box tool
        print("Calling tool: message_box")
        result = run_command("call_tool", {
            "tool_name": "message_box",
            "params": {"message": "Test message from MCP client at " + time.ctime()}
        })
        
        if result and "success" in result and result["success"]:
            print(f"✓ Tool 'message_box' called successfully")
            if "result" in result:
                print(f"  Result: {result['result']}")
        else:
            print(f"✗ Tool 'message_box' failed")
        
        # Test create_new_sketch tool
        print("Calling tool: create_new_sketch")
        result = run_command("call_tool", {
            "tool_name": "create_new_sketch",
            "params": {"plane_name": "XY"}
        })
        
        if result and "success" in result and result["success"]:
            print(f"✓ Tool 'create_new_sketch' called successfully")
            if "result" in result:
                print(f"  Result: {result['result']}")
        else:
            print(f"✗ Tool 'create_new_sketch' failed")
        
        # Test create_parameter tool
        print("Calling tool: create_parameter")
        result = run_command("call_tool", {
            "tool_name": "create_parameter",
            "params": {
                "name": f"TestParam_{int(time.time()) % 10000}",
                "expression": "10 mm",
                "unit": "mm",
                "comment": "Created by MCP client test"
            }
        })
        
        if result and "success" in result and result["success"]:
            print(f"✓ Tool 'create_parameter' called successfully")
            if "result" in result:
                print(f"  Result: {result['result']}")
        else:
            print(f"✗ Tool 'create_parameter' failed")
    else:
        print("Failed to list tools")

def test_prompts():
    """Test the prompts provided by the server using file-based communication."""
    print("\nTesting prompts...")
    
    # List prompts
    prompt_list = run_command("list_prompts")
    if prompt_list and "prompts" in prompt_list:
        print(f"Available prompts: {prompt_list['prompts']}")
        
        # Test specific prompts
        for prompt_name in ["create_sketch_prompt", "parameter_setup_prompt"]:
            print(f"Requesting prompt: {prompt_name}")
            result = run_command("get_prompt", {"prompt_name": prompt_name})
            
            if result and "success" in result and result["success"]:
                print(f"✓ Prompt '{prompt_name}' available")
                if "content" in result:
                    content = result["content"]
                    prompt_lines = content.split('\n')
                    preview = '\n'.join(prompt_lines[:min(3, len(prompt_lines))])
                    print(f"  Content preview: {preview}...")
            else:
                print(f"✗ Prompt '{prompt_name}' not available")
    else:
        print("Failed to list prompts")

def test_message_box():
    """Test the message_box functionality by creating a file that Fusion 360 can detect."""
    print("\nTesting message box functionality through file...")
    
    # Create a file with a message that Fusion 360 can read
    message_file_path = COMM_DIR / "message_box.txt"
    
    try:
        with open(message_file_path, "w") as f:
            f.write(f"DISPLAY_MESSAGE: Test message from MCP client at {time.ctime()}")
        
        print(f"Created message file at: {message_file_path}")
        print("If the Fusion 360 add-in is monitoring this file, it should display a message box.")
        
        # Also try through the command system
        run_command("message_box", {"message": f"Command file message at {time.ctime()}"})
        
    except Exception as e:
        print(f"Error creating message file: {str(e)}")

def check_server_ready(wait_time):
    """Check if the server is ready by looking for the ready file."""
    print(f"Waiting up to {wait_time} seconds for server to be ready...")
    
    # Get the current directory and parent directories
    current_dir = Path(__file__).resolve().parent
    parent_dir = current_dir.parent
    
    # Look for ready file in different common locations
    potential_paths = [
        # In the Fusion add-in directories
        FUSION_ADDIN_PATH / "MCPserve" / "mcp_server_ready.txt",
        FUSION_ADDIN_PATH / "mcp_server_ready.txt",
        FUSION_MCP_COMM_DIR / "mcp_server_ready.txt",
        
        # In the same directory as this script
        current_dir / "mcp_server_ready.txt",
        # In the MCP Server Script directory
        current_dir / "MCP Server Script" / "mcp_server_ready.txt",
        # In the communication directory
        COMM_DIR / "mcp_server_ready.txt",
        LOCAL_MCP_COMM_DIR / "mcp_server_ready.txt",
        # One level up from script directory
        parent_dir / "mcp_server_ready.txt",
        # User desktop
        Path.home() / "Desktop" / "mcp_server_ready.txt",
    ]
    
    # Print all paths we're checking
    print("Checking for ready file in these locations:")
    for path in potential_paths:
        print(f"- {path}")
    
    start_time = time.time()
    found = False
    found_path = None
    
    while time.time() - start_time < wait_time:
        for path in potential_paths:
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        content = f.read().strip()
                    print(f"Server is ready! Found indicator file: {path}")
                    print(f"Content: {content}")
                    found = True
                    found_path = path
                    break
                except Exception as e:
                    print(f"Error reading file {path}: {str(e)}")
        
        if found:
            break
            
        time.sleep(0.5)
    
    if not found:
        print("WARNING: Server ready file not found. Server might not be running or ready.")
        user_input = input("Continue anyway? (y/n): ")
        if user_input.lower() != 'y':
            sys.exit(1)
    
    return found_path

def run_file_based_tests():
    """Run tests using file-based communication."""
    print("Running tests using file-based communication...")
    
    # Create the ready file to let the server know we're testing
    ready_file = COMM_DIR / "client_ready.txt"
    try:
        with open(ready_file, "w") as f:
            f.write(f"Client ready for testing at {time.ctime()}")
        print(f"Created client ready file: {ready_file}")
    except Exception as e:
        print(f"Error creating client ready file: {str(e)}")
    
    # Run the tests
    try:
        # Test resources
        test_resources()
        
        # Test tools
        test_tools()
        
        # Test prompts
        test_prompts()
        
        # Test message box
        test_message_box()
        
        print("\nAll tests completed!")
    except Exception as e:
        print(f"Error during tests: {str(e)}")
        print(traceback.format_exc())

def main():
    """Main entry point for the client."""
    parser = argparse.ArgumentParser(description='MCP Client for Fusion 360')
    parser.add_argument('--wait', type=int, default=10, 
                        help='Time to wait in seconds for server to be ready')
    args = parser.parse_args()
    
    print("MCP Client for Fusion 360")
    print("=========================")
    
    # Clear old command and response files
    for file in COMM_DIR.glob("command_*.json"):
        file.unlink()
    for file in COMM_DIR.glob("response_*.json"):
        file.unlink()
    
    # Wait for server to be ready
    found_ready_file = check_server_ready(args.wait)
    
    # Run our tests using file-based communication
    run_file_based_tests()
    
    print("\nTest completed.")

if __name__ == "__main__":
    main() 