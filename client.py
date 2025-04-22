#!/usr/bin/env python3

"""
MCP Client for Fusion 360

Client to interact with the Fusion 360 MCP server.
This client supports both the MCP SDK connection method and file-based communication.
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
import urllib.request
import asyncio
from typing import Optional, Dict, List, Any, Tuple

# Print debugging information
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")

# Find the location of the MCP package
try:
    import mcp
    print(f"Found MCP package at: {mcp.__file__}")
except ImportError as e:
    print(f"MCP package not found. Error: {str(e)}")
    print("You may need to install it with: pip install mcp[cli]")
    mcp = None

# Parse command line arguments
parser = argparse.ArgumentParser(description="Interact with the Fusion 360 MCP server")
parser.add_argument("--url", default="http://127.0.0.1:3000/sse", help="Server SSE URL (default: %(default)s)")
parser.add_argument("--timeout", type=int, default=10, help="Connection timeout in seconds (default: %(default)s)")
parser.add_argument("--verbose", action="store_true", help="Print verbose output")
parser.add_argument("--use-sdk", action="store_true", help="Use MCP SDK for communication (requires mcp package)")
parser.add_argument("--test-connection", action="store_true", help="Test connection to the server")
parser.add_argument("--test-message-box", action="store_true", help="Test message box functionality")
parser.add_argument("--message", type=str, help="Custom message to display when testing message box")
parser.add_argument("--list-resources", action="store_true", help="List available resources")
parser.add_argument("--list-tools", action="store_true", help="List available tools")
parser.add_argument("--list-prompts", action="store_true", help="List available prompts")
parser.add_argument("--wait-ready", action="store_true", help="Wait for the server to be ready before running tests")
parser.add_argument("--test-resource", type=str, help="Test a specific resource by URI (e.g., fusion://active-document-info)")
parser.add_argument("--test-sketch", action="store_true", help="Test the create_new_sketch tool")
parser.add_argument("--plane", type=str, default="XY", help="Plane to use for sketch creation test (default: XY)")
parser.add_argument("--test-parameter", action="store_true", help="Test the create_parameter tool")
parser.add_argument("--param-name", type=str, help="Name for the test parameter")
parser.add_argument("--param-expression", type=str, default="10", help="Expression for the test parameter (default: 10)")
parser.add_argument("--param-unit", type=str, default="mm", help="Unit for the test parameter (default: mm)")
parser.add_argument("--test-prompt", type=str, help="Test a specific prompt by name (e.g., create_sketch_prompt)")
parser.add_argument("--prompt-args", type=str, help="JSON string of arguments for the prompt test")
parser.add_argument("--test-all", action="store_true", help="Run all available tests")
args = parser.parse_args()

# Set up paths for communication
WORKSPACE_PATH = Path(__file__).parent
COMM_DIR = WORKSPACE_PATH / "mcp_comm"
COMM_DIR.mkdir(exist_ok=True)

class MCPClient:
    """Client for interacting with the Fusion 360 MCP server."""
    
    def __init__(self, sse_url: str = "http://127.0.0.1:3000/sse", timeout: int = 10, use_sdk: bool = False):
        self.sse_url = sse_url
        self.timeout = timeout
        self.use_sdk = use_sdk and mcp is not None
        self.connected = False
        self.session = None
    
    async def connect(self) -> bool:
        """Connect to the MCP server."""
        if self.use_sdk:
            try:
                from mcp import ClientSession, HttpServerParameters
                
                # Create server parameters for HTTP connection
                server_params = HttpServerParameters(
                    base_url=self.sse_url,
                    timeout=self.timeout
                )
                
                # Create a client session
                self.session = ClientSession.create_http_session(server_params)
                
                # Initialize the connection
                await self.session.initialize()
                
                self.connected = True
                return True
            except ImportError as e:
                print(f"Error importing MCP client modules: {str(e)}")
                print("Falling back to direct connection method")
            except Exception as e:
                print(f"Error connecting to MCP server using SDK: {str(e)}")
                print("Falling back to direct connection method")
        
        # If SDK connection failed or was not requested, try direct HTTP connection
        try:
            with urllib.request.urlopen(self.sse_url, timeout=self.timeout) as response:
                if response.getcode() == 200:
                    self.connected = True
                    return True
        except Exception as e:
            print(f"Error connecting to MCP server via HTTP: {str(e)}")
        
        return False
    
    async def test_connection(self) -> Tuple[bool, str]:
        """Test the connection to the server."""
        print(f"Testing connection to server at {self.sse_url}...")
        
        # Try multiple connection methods to be thorough
        error_messages = []
        
        # Method 1: Direct HTTP HEAD request
        try:
            print("Trying direct HTTP head request...")
            # First try to connect to the HTTP endpoint
            http_url = self.sse_url.replace("/sse", "/")
            req = urllib.request.Request(http_url, method="HEAD")
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                print(f"HTTP connection successful. Status code: {response.getcode()}")
                return True, f"Connected to server at {http_url}"
        except Exception as e:
            error_message = f"HTTP HEAD request failed: {str(e)}"
            print(error_message)
            error_messages.append(error_message)
        
        # Method 2: Direct HTTP GET request
        try:
            print("Trying direct HTTP GET request...")
            http_url = self.sse_url.replace("/sse", "/")
            req = urllib.request.Request(http_url, method="GET")
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                print(f"HTTP GET request successful. Status code: {response.getcode()}")
                content = response.read().decode('utf-8')
                print(f"Response content: {content[:200]}...")  # Print first 200 chars
                return True, f"Connected to server at {http_url}"
        except Exception as e:
            error_message = f"HTTP GET request failed: {str(e)}"
            print(error_message)
            error_messages.append(error_message)
        
        # Method 3: Direct SSE endpoint GET request
        try:
            print("Trying direct SSE endpoint request...")
            req = urllib.request.Request(self.sse_url, method="GET")
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                print(f"SSE endpoint request successful. Status code: {response.getcode()}")
                # Don't read the content as it might block
                return True, f"SSE endpoint available at {self.sse_url}"
        except Exception as e:
            error_message = f"SSE endpoint request failed: {str(e)}"
            print(error_message)
            error_messages.append(error_message)
        
        # Method 4: SDK connection if available
        if self.use_sdk:
            try:
                print("Trying MCP SDK connection...")
                success = await self.connect()
                if success:
                    return True, f"Connected to server at {self.sse_url} using MCP SDK"
                error_message = "Failed to connect using MCP SDK"
                print(error_message)
                error_messages.append(error_message)
            except Exception as e:
                error_message = f"Error connecting using MCP SDK: {str(e)}"
                print(error_message)
                error_messages.append(error_message)
        
        # Method 5: File-based connection as a last resort
        print("Trying file-based communication as a last resort...")
        success, result = await self.test_file_connection()
        if success:
            return True, "Connected using file-based communication"
        
        # All methods failed
        return False, "All connection methods failed. Errors:\n" + "\n".join(error_messages)
    
    async def test_file_connection(self) -> Tuple[bool, Any]:
        """Test file-based communication with the server."""
        # Create a test command file
        command_id = int(time.time() * 1000)
        command_file = COMM_DIR / f"command_{command_id}.json"
        response_file = COMM_DIR / f"response_{command_id}.json"
        
        # Remove existing response file if it exists
        if response_file.exists():
            response_file.unlink()
        
        # Create command data
        command_data = {
            "command": "list_resources",
            "params": {}
        }
        
        # Write command file
        with open(command_file, "w") as f:
            json.dump(command_data, f, indent=2)
        
        print(f"Created test command file: {command_file}")
        
        # Wait for response
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            if response_file.exists():
                try:
                    with open(response_file, "r") as f:
                        response = json.load(f)
                    return True, response
                except Exception as e:
                    return False, f"Error reading response: {str(e)}"
            await asyncio.sleep(0.1)
        
        return False, "Timeout waiting for response"
    
    async def list_resources(self) -> List[str]:
        """Get a list of available resources from the server."""
        if self.use_sdk and self.session:
            try:
                resources = await self.session.list_resources()
                return resources
            except Exception as e:
                print(f"Error listing resources using SDK: {str(e)}")
                print("Falling back to file-based method")
        
        # Use file-based communication
        command_id = int(time.time() * 1000)
        command_file = COMM_DIR / f"command_{command_id}.json"
        response_file = COMM_DIR / f"response_{command_id}.json"
        
        # Create command data
        command_data = {
            "command": "list_resources",
            "params": {}
        }
        
        # Write command file
        with open(command_file, "w") as f:
            json.dump(command_data, f, indent=2)
        
        print(f"Created list_resources command file: {command_file}")
        
        # Wait for response
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            if response_file.exists():
                with open(response_file, "r") as f:
                    response = json.load(f)
                return response.get("result", [])
            await asyncio.sleep(0.1)
        
        return []
    
    async def list_tools(self) -> List[Dict[str, str]]:
        """Get a list of available tools from the server."""
        if self.use_sdk and self.session:
            try:
                tools = await self.session.list_tools()
                return [{"name": tool, "description": ""} for tool in tools]
            except Exception as e:
                print(f"Error listing tools using SDK: {str(e)}")
                print("Falling back to file-based method")
        
        # Use file-based communication
        command_id = int(time.time() * 1000)
        command_file = COMM_DIR / f"command_{command_id}.json"
        response_file = COMM_DIR / f"response_{command_id}.json"
        
        # Create command data
        command_data = {
            "command": "list_tools",
            "params": {}
        }
        
        # Write command file
        with open(command_file, "w") as f:
            json.dump(command_data, f, indent=2)
        
        print(f"Created list_tools command file: {command_file}")
        
        # Wait for response
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            if response_file.exists():
                with open(response_file, "r") as f:
                    response = json.load(f)
                return response.get("result", [])
            await asyncio.sleep(0.1)
        
        return []
    
    async def list_prompts(self) -> List[Dict[str, str]]:
        """Get a list of available prompts from the server."""
        if self.use_sdk and self.session:
            try:
                prompts = await self.session.list_prompts()
                return [{"name": prompt.name, "description": prompt.description} for prompt in prompts]
            except Exception as e:
                print(f"Error listing prompts using SDK: {str(e)}")
                print("Falling back to file-based method")
        
        # Use file-based communication
        command_id = int(time.time() * 1000)
        command_file = COMM_DIR / f"command_{command_id}.json"
        response_file = COMM_DIR / f"response_{command_id}.json"
        
        # Create command data
        command_data = {
            "command": "list_prompts",
            "params": {}
        }
        
        # Write command file
        with open(command_file, "w") as f:
            json.dump(command_data, f, indent=2)
        
        print(f"Created list_prompts command file: {command_file}")
        
        # Wait for response
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            if response_file.exists():
                with open(response_file, "r") as f:
                    response = json.load(f)
                return response.get("result", [])
            await asyncio.sleep(0.1)
        
        return []
    
    async def call_tool(self, tool_name: str, **params) -> Any:
        """Call a tool on the server."""
        if self.use_sdk and self.session:
            try:
                result = await self.session.call_tool(tool_name, arguments=params)
                return result
            except Exception as e:
                print(f"Error calling tool using SDK: {str(e)}")
                print("Falling back to file-based method")
        
        # Use file-based communication
        command_id = int(time.time() * 1000)
        command_file = COMM_DIR / f"command_{command_id}.json"
        response_file = COMM_DIR / f"response_{command_id}.json"
        
        # Create command data
        command_data = {
            "command": tool_name,
            "params": params
        }
        
        # Write command file
        with open(command_file, "w") as f:
            json.dump(command_data, f, indent=2)
        
        print(f"Created {tool_name} command file: {command_file}")
        
        # Wait for response
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            if response_file.exists():
                with open(response_file, "r") as f:
                    response = json.load(f)
                return response.get("result", None)
            await asyncio.sleep(0.1)
        
        return None
    
    async def test_message_box(self, message: str = None) -> Tuple[bool, str]:
        """Test the message box functionality with verification."""
        if message is None:
            message = f"MCP Test Message - {time.ctime()}"
        
        print(f"Testing message box...")
        print(f"Displaying message: {message}")
        
        # Create unique timestamp to track this specific message
        timestamp = int(time.time())
        message_id = f"test_msg_{timestamp}"
        
        # Method 1: Try file-based communication first
        try:
            # Create command file with the message_id included in the message
            command_id = int(time.time() * 1000)
            command_file = COMM_DIR / f"command_{command_id}.json"
            
            # Include a unique identifier in the message to track it
            tagged_message = f"{message} [ID:{message_id}]"
            
            # Create command data
            command_data = {
                "command": "message_box",
                "params": {
                    "message": tagged_message
                }
            }
            
            # Write command file
            with open(command_file, "w") as f:
                json.dump(command_data, f, indent=2)
            
            print(f"Created message_box command file: {command_file}")
            
            # Also create a direct message file as backup
            message_file = COMM_DIR / "message_box.txt"
            with open(message_file, "w") as f:
                f.write(tagged_message)
            
            print(f"Created message file: {message_file}")
            
            # Wait for processed message file to appear
            processed_prefix = "processed_message_"
            response_file = COMM_DIR / f"response_{command_id}.json"
            
            start_time = time.time()
            
            # Look for either a processed message file or a response to our command
            while time.time() - start_time < self.timeout:
                # Check for processed message files
                for file in os.listdir(COMM_DIR):
                    if file.startswith(processed_prefix) and file.endswith(".txt"):
                        processed_path = COMM_DIR / file
                        
                        # Check if this is our message by reading content
                        try:
                            with open(processed_path, "r") as f:
                                content = f.read()
                                if message_id in content:
                                    print(f"✅ Found processed message file: {processed_path}")
                                    print(f"Message was displayed in Fusion 360")
                                    return True, "Message box displayed successfully"
                        except Exception as e:
                            print(f"Error reading processed file {processed_path}: {str(e)}")
                
                # Check for response to our command
                if response_file.exists():
                    try:
                        with open(response_file, "r") as f:
                            response = json.load(f)
                            result = response.get("result", "")
                            
                            if "success" in result.lower():
                                print(f"✅ Received success response from server")
                                return True, "Message box display command acknowledged by server"
                            else:
                                print(f"❌ Received response but not success: {result}")
                    except Exception as e:
                        print(f"Error reading response file: {str(e)}")
                
                # Check if original message file is gone (possibly processed)
                if not message_file.exists() and not os.path.exists(command_file):
                    print(f"✅ Message file was processed (no longer exists)")
                    return True, "Message file was processed by server"
                
                # Wait a bit before checking again
                await asyncio.sleep(0.2)
            
            print(f"❌ Timeout waiting for message box confirmation")
            
            # If we get here, we didn't find confirmation
            if response_file.exists():
                try:
                    with open(response_file, "r") as f:
                        response = json.load(f)
                        print(f"Server response: {response}")
                        if "error" in response:
                            return False, f"Server error: {response['error']}"
                except:
                    pass
            
            return False, "Timeout waiting for message box confirmation. The server may not be processing message commands."
            
        except Exception as e:
            error_message = f"Error testing message box: {str(e)}"
            print(f"❌ {error_message}")
            return False, error_message
    
    async def test_resource(self, resource_uri: str) -> Tuple[bool, str, Any]:
        """Test reading a specific resource from the server.
        
        Args:
            resource_uri: The URI of the resource to read
            
        Returns:
            Tuple of (success, message, content)
        """
        print(f"Testing resource: {resource_uri}")
        
        try:
            # Try to read the resource using file-based communication
            command_id = int(time.time() * 1000)
            command_file = COMM_DIR / f"command_{command_id}.json"
            response_file = COMM_DIR / f"response_{command_id}.json"
            
            # Create command data
            command_data = {
                "command": "read_resource",
                "params": {
                    "uri": resource_uri
                }
            }
            
            # Write command file
            with open(command_file, "w") as f:
                json.dump(command_data, f, indent=2)
            
            print(f"Created read_resource command file for {resource_uri}")
            
            # Wait for response
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                if response_file.exists():
                    try:
                        with open(response_file, "r") as f:
                            response = json.load(f)
                        
                        # Check if there's an error
                        if "error" in response:
                            return False, f"Error reading resource: {response['error']}", None
                        
                        result = response.get("result", None)
                        if result is not None:
                            return True, f"Successfully read resource: {resource_uri}", result
                        else:
                            return False, "No result in response", None
                    except Exception as e:
                        return False, f"Error parsing response: {str(e)}", None
                await asyncio.sleep(0.1)
            
            return False, f"Timeout waiting for response when reading {resource_uri}", None
        except Exception as e:
            error_message = f"Error testing resource {resource_uri}: {str(e)}"
            print(f"❌ {error_message}")
            return False, error_message, None
    
    async def test_create_sketch_tool(self, plane_name: str = "XY") -> Tuple[bool, str]:
        """Test the create_new_sketch tool with the given plane.
        
        Args:
            plane_name: The name of the plane to create the sketch on (default: "XY")
            
        Returns:
            Tuple of (success, message)
        """
        print(f"Testing create_new_sketch tool with plane: {plane_name}")
        
        try:
            # Use file-based communication
            command_id = int(time.time() * 1000)
            command_file = COMM_DIR / f"command_{command_id}.json"
            response_file = COMM_DIR / f"response_{command_id}.json"
            
            # Create command data
            command_data = {
                "command": "create_new_sketch",
                "params": {
                    "plane_name": plane_name
                }
            }
            
            # Write command file
            with open(command_file, "w") as f:
                json.dump(command_data, f, indent=2)
            
            print(f"Created create_new_sketch command file with plane: {plane_name}")
            
            # Wait for response
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                if response_file.exists():
                    try:
                        with open(response_file, "r") as f:
                            response = json.load(f)
                        
                        # Check if there's an error
                        if "error" in response:
                            return False, f"Error creating sketch: {response['error']}"
                        
                        result = response.get("result", "")
                        if "successfully" in result.lower():
                            return True, result
                        else:
                            return False, f"Unexpected result: {result}"
                    except Exception as e:
                        return False, f"Error parsing response: {str(e)}"
                await asyncio.sleep(0.1)
            
            return False, f"Timeout waiting for response when creating sketch on {plane_name}"
        except Exception as e:
            error_message = f"Error testing create_new_sketch tool: {str(e)}"
            print(f"❌ {error_message}")
            return False, error_message

    async def test_create_parameter_tool(self, name: str = None, expression: str = "10", unit: str = "mm", comment: str = "Test parameter") -> Tuple[bool, str]:
        """Test the create_parameter tool with the given parameters.
        
        Args:
            name: The name of the parameter (default: auto-generated)
            expression: The parameter expression (default: "10")
            unit: The parameter unit (default: "mm")
            comment: The parameter comment (default: "Test parameter")
            
        Returns:
            Tuple of (success, message)
        """
        if name is None:
            name = f"TestParam_{int(time.time()) % 10000}"
        
        print(f"Testing create_parameter tool with name: {name}, expression: {expression}, unit: {unit}")
        
        try:
            # Use file-based communication
            command_id = int(time.time() * 1000)
            command_file = COMM_DIR / f"command_{command_id}.json"
            response_file = COMM_DIR / f"response_{command_id}.json"
            
            # Create command data
            command_data = {
                "command": "create_parameter",
                "params": {
                    "name": name,
                    "expression": expression,
                    "unit": unit,
                    "comment": comment
                }
            }
            
            # Write command file
            with open(command_file, "w") as f:
                json.dump(command_data, f, indent=2)
            
            print(f"Created create_parameter command file for {name}")
            
            # Wait for response
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                if response_file.exists():
                    try:
                        with open(response_file, "r") as f:
                            response = json.load(f)
                        
                        # Check if there's an error
                        if "error" in response:
                            return False, f"Error creating parameter: {response['error']}"
                        
                        result = response.get("result", "")
                        if "successfully" in result.lower() or "created" in result.lower():
                            return True, result
                        else:
                            return False, f"Unexpected result: {result}"
                    except Exception as e:
                        return False, f"Error parsing response: {str(e)}"
                await asyncio.sleep(0.1)
            
            return False, f"Timeout waiting for response when creating parameter {name}"
        except Exception as e:
            error_message = f"Error testing create_parameter tool: {str(e)}"
            print(f"❌ {error_message}")
            return False, error_message

    async def test_prompt(self, prompt_name: str, **prompt_args) -> Tuple[bool, str, Any]:
        """Test retrieving a prompt from the server.
        
        Args:
            prompt_name: The name of the prompt to retrieve
            **prompt_args: Arguments for the prompt
            
        Returns:
            Tuple of (success, message, content)
        """
        print(f"Testing prompt: {prompt_name} with args: {prompt_args}")
        
        try:
            # Try to get the prompt using file-based communication
            command_id = int(time.time() * 1000)
            command_file = COMM_DIR / f"command_{command_id}.json"
            response_file = COMM_DIR / f"response_{command_id}.json"
            
            # Create command data
            command_data = {
                "command": "get_prompt",
                "params": {
                    "name": prompt_name,
                    "args": prompt_args
                }
            }
            
            # Write command file
            with open(command_file, "w") as f:
                json.dump(command_data, f, indent=2)
            
            print(f"Created get_prompt command file for {prompt_name}")
            
            # Wait for response
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                if response_file.exists():
                    try:
                        with open(response_file, "r") as f:
                            response = json.load(f)
                        
                        # Check if there's an error
                        if "error" in response:
                            return False, f"Error getting prompt: {response['error']}", None
                        
                        result = response.get("result", None)
                        if result is not None:
                            # Check if the result has the expected structure
                            if isinstance(result, dict) and "messages" in result:
                                return True, f"Successfully retrieved prompt: {prompt_name}", result
                            else:
                                return False, f"Invalid prompt format: {result}", result
                        else:
                            return False, "No result in response", None
                    except Exception as e:
                        return False, f"Error parsing response: {str(e)}", None
                await asyncio.sleep(0.1)
            
            return False, f"Timeout waiting for response when getting prompt {prompt_name}", None
        except Exception as e:
            error_message = f"Error testing prompt {prompt_name}: {str(e)}"
            print(f"❌ {error_message}")
            return False, error_message, None
    
    async def close(self):
        """Close the connection to the server."""
        if self.session:
            await self.session.close()
            self.session = None
        self.connected = False

async def run_tests(client: MCPClient, server_status=None):
    """Run a series of tests against the MCP server."""
    print("\n=== FUSION 360 MCP SERVER TESTS ===\n")
    
    # Test connection
    print("Testing connection to MCP server...")
    success, message = await client.test_connection()
    if success:
        print(f"✅ Connection successful: {message}")
    else:
        print(f"❌ Connection failed: {message}")
        return False
    
    # If we have server_status data, we can use it instead of making server calls
    if server_status and server_status.get('status') == 'running':
        print("\nUsing server status information from server_status.json file:")
        
        # Resources
        resources = server_status.get('resources', [])
        if resources:
            print(f"\n✅ Found {len(resources)} resources:")
            for resource in resources:
                print(f"  - {resource}")
        else:
            print("\n❌ No resources found in server status")
        
        # Tools
        tools = server_status.get('tools', [])
        if tools:
            print(f"\n✅ Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool['name']}: {tool.get('description', '')}")
        else:
            print("\n❌ No tools found in server status")
        
        # Prompts
        prompts = server_status.get('prompts', [])
        if prompts:
            print(f"\n✅ Found {len(prompts)} prompts:")
            for prompt in prompts:
                print(f"  - {prompt['name']}: {prompt.get('description', '')}")
        else:
            print("\n❌ No prompts found in server status")
    else:
        # No server status or not running, so query server directly
        
        # Test listing resources
        print("\nListing resources...")
        resources = await client.list_resources()
        if resources:
            print(f"✅ Found {len(resources)} resources:")
            for resource in resources:
                print(f"  - {resource}")
        else:
            print("❌ No resources found or error occurred")
        
        # Test listing tools
        print("\nListing tools...")
        tools = await client.list_tools()
        if tools:
            print(f"✅ Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool['name']}: {tool.get('description', '')}")
        else:
            print("❌ No tools found or error occurred")
        
        # Test listing prompts
        print("\nListing prompts...")
        prompts = await client.list_prompts()
        if prompts:
            print(f"✅ Found {len(prompts)} prompts:")
            for prompt in prompts:
                print(f"  - {prompt['name']}: {prompt.get('description', '')}")
        else:
            print("❌ No prompts found or error occurred")
    
    # Test message box in either case
    print("\nTesting message box...")
    message_result = await client.test_message_box()
    if message_result:
        print("✅ Message box displayed successfully")
    else:
        print("❌ Failed to display message box")
    
    return True

async def main():
    """Main function."""
    print("\n=== FUSION 360 MCP SERVER TESTS ===\n")
    
    # Track test results
    test_results = {}
    
    # Check for server status file
    status_file = COMM_DIR / "server_status.json"
    server_status = None
    if status_file.exists():
        try:
            with open(status_file, "r") as f:
                server_status = json.load(f)
                print("Found server status file:")
                print(f"  Status: {server_status.get('status', 'unknown')}")
                print(f"  Last updated: {server_status.get('started_at', 'unknown')}")
                print(f"  Server URL: {server_status.get('server_url', 'unknown')}")
                print()
        except Exception as e:
            print(f"Error reading server status file: {str(e)}")
    
    # Add a direct message box test for debugging
    # Create a message_box.txt file directly
    try:
        test_message = "DIRECT TEST MESSAGE from client.py - " + time.ctime()
        message_file = COMM_DIR / "message_box.txt"
        with open(message_file, "w") as f:
            f.write(test_message)
        print(f"Created direct test message file: {message_file}")
        print(f"Test message: {test_message}")
        print("If this message appears in Fusion 360, the direct message mechanism is working.")
        print()
    except Exception as e:
        print(f"Error creating direct test message: {str(e)}")
    
    # Check for error files
    error_file = COMM_DIR / "mcp_server_error.txt"
    if error_file.exists():
        try:
            with open(error_file, "r") as f:
                error_content = f.read().strip()
                print("⚠️ Server error detected:")
                print(error_content)
                print("\nThe server might not be functioning correctly.")
                print()
        except Exception as e:
            print(f"Error reading error file: {str(e)}")
    
    # Create client
    client = MCPClient(sse_url=args.url, timeout=args.timeout, use_sdk=args.use_sdk)
    
    # Wait for ready file if requested
    if args.wait_ready:
        print("Waiting for server ready file...")
        ready_files = [
            WORKSPACE_PATH / "mcp_server_ready.txt",
            COMM_DIR / "mcp_server_ready.txt",
            Path.home() / "Desktop" / "mcp_server_ready.txt"
        ]
        
        start_time = time.time()
        while time.time() - start_time < args.timeout:
            for ready_file in ready_files:
                if ready_file.exists():
                    try:
                        with open(ready_file, "r") as f:
                            content = f.read().strip()
                        print(f"✅ Server ready: {content}")
                        break
                    except:
                        pass
            else:
                # Continue waiting if no file found
                await asyncio.sleep(0.5)
                continue
            
            # If we're here, we found a ready file
            break
        else:
            print("❌ Timeout waiting for server ready file")
    
    # Determine if specific tests were requested
    specific_tests = args.test_connection or args.test_message_box or args.list_resources or \
                     args.list_tools or args.list_prompts or args.test_resource or \
                     args.test_sketch or args.test_parameter or args.test_prompt or args.test_all
    
    # Test connection if requested or if running all tests
    if args.test_connection or args.test_all or not specific_tests:
        print("\n=== CONNECTION TEST ===")
        success, message = await client.test_connection()
        if success:
            print(f"✅ Connection successful: {message}")
            test_results["connection"] = True
        else:
            print(f"❌ Connection failed: {message}")
            test_results["connection"] = False
    
    # Get available resources, tools, and prompts from status file
    available_resources = []
    available_tools = []
    available_prompts = []
    
    if server_status:
        available_resources = server_status.get("available_resources", [])
        available_tools = server_status.get("available_tools", [])
        available_prompts = server_status.get("available_prompts", [])
    
    # List resources if requested
    if args.list_resources or args.test_all or not specific_tests:
        print("\n=== AVAILABLE RESOURCES ===")
        if available_resources:
            for resource in available_resources:
                print(f"  - {resource}")
        else:
            # Try to get from server
            resources = await client.list_resources()
            if resources:
                for resource in resources:
                    print(f"  - {resource}")
                # Update available resources
                available_resources = resources
            else:
                print("❌ No resources found")
        print()
    
    # List tools if requested
    if args.list_tools or args.test_all or not specific_tests:
        print("\n=== AVAILABLE TOOLS ===")
        if available_tools:
            for tool in available_tools:
                print(f"  - {tool}")
        else:
            # Try to get from server
            tools = await client.list_tools()
            if tools:
                for tool in tools:
                    if isinstance(tool, dict):
                        print(f"  - {tool.get('name')}: {tool.get('description', '')}")
                    else:
                        print(f"  - {tool}")
                # Update available tools
                available_tools = [t.get('name') if isinstance(t, dict) else t for t in tools]
            else:
                print("❌ No tools found")
        print()
    
    # List prompts if requested
    if args.list_prompts or args.test_all or not specific_tests:
        print("\n=== AVAILABLE PROMPTS ===")
        if available_prompts:
            for prompt in available_prompts:
                print(f"  - {prompt}")
        else:
            # Try to get from server
            prompts = await client.list_prompts()
            if prompts:
                for prompt in prompts:
                    if isinstance(prompt, dict):
                        print(f"  - {prompt.get('name')}: {prompt.get('description', '')}")
                    else:
                        print(f"  - {prompt}")
                # Update available prompts
                available_prompts = [p.get('name') if isinstance(p, dict) else p for p in prompts]
            else:
                print("❌ No prompts found")
        print()
    
    # Test specific resource if requested or all resources if test_all
    if args.test_resource or args.test_all:
        resources_to_test = []
        if args.test_resource:
            resources_to_test = [args.test_resource]
        elif args.test_all and available_resources:
            resources_to_test = available_resources
        
        if resources_to_test:
            print("\n=== RESOURCE TESTS ===")
            resource_results = {}
            for resource_uri in resources_to_test:
                success, message, content = await client.test_resource(resource_uri)
                resource_results[resource_uri] = success
                if success:
                    print(f"✅ Resource {resource_uri}: {message}")
                    if args.verbose:
                        print("Content:")
                        print(json.dumps(content, indent=2, ensure_ascii=False)[:500] + "..." if len(json.dumps(content)) > 500 else json.dumps(content, indent=2, ensure_ascii=False))
                else:
                    print(f"❌ Resource {resource_uri}: {message}")
            test_results["resources"] = resource_results
            print()
    
    # Test message box if requested or if running all tests
    if args.test_message_box or args.test_all or not specific_tests:
        print("\n=== MESSAGE BOX TEST ===")
        print("⚠️ NOTE: Even if this test reports success, please verify that you actually see")
        print("a message box pop up in Fusion 360. This test can give false positives if the")
        print("server processes the command file but fails to display the actual message box.\n")
        
        message = args.message if args.message else None
        success, result = await client.test_message_box(message)
        test_results["message_box"] = success
        if success:
            print(f"✅ Message box test appears successful: {result}")
            print("\n⚠️ IMPORTANT: Did you actually see a message box in Fusion 360?")
            print("If not, the server may not be functioning correctly despite this 'success' report.")
        else:
            print(f"❌ Message box test failed: {result}")
            print("\nCheck that Fusion 360 is running and the MCP Server add-in is active.")
        print()
    
    # Test sketch creation if requested or if running all tests
    if args.test_sketch or args.test_all:
        print("\n=== CREATE SKETCH TEST ===")
        print("⚠️ NOTE: This test can fail if you don't have a design document open in Fusion 360.")
        print("Please make sure you have an active design document open before running this test.\n")
        
        plane = args.plane
        success, result = await client.test_create_sketch_tool(plane)
        test_results["create_sketch"] = success
        if success:
            print(f"✅ Create sketch test successful: {result}")
            print("\nPlease check that a new sketch was actually created in Fusion 360.")
        else:
            print(f"❌ Create sketch test failed: {result}")
            if "no active document" in result.lower() or "not a design document" in result.lower():
                print("\nCommon issues:")
                print("1. You need to have Fusion 360 running with a design document open.")
                print("2. The active document must be a design document, not a drawing or CAM document.")
                print("3. Make sure the MCP server add-in is running.")
        print()
    
    # Test parameter creation if requested or if running all tests
    if args.test_parameter or args.test_all:
        print("\n=== CREATE PARAMETER TEST ===")
        print("⚠️ NOTE: This test can fail if you don't have a design document open in Fusion 360.")
        print("Please make sure you have an active design document open before running this test.\n")
        
        name = args.param_name
        expression = args.param_expression
        unit = args.param_unit
        success, result = await client.test_create_parameter_tool(name, expression, unit)
        test_results["create_parameter"] = success
        if success:
            print(f"✅ Create parameter test successful: {result}")
            print("\nPlease check that a new parameter was actually created in Fusion 360.")
        else:
            print(f"❌ Create parameter test failed: {result}")
            if "no active document" in result.lower() or "not a design document" in result.lower():
                print("\nCommon issues:")
                print("1. You need to have Fusion 360 running with a design document open.")
                print("2. The active document must be a design document, not a drawing or CAM document.")
                print("3. Make sure the MCP server add-in is running.")
            elif "parameter exists" in result.lower():
                print("\nA parameter with this name already exists. Try using a different name.")
        print()
    
    # Test specific prompt if requested or all prompts if test_all
    if args.test_prompt or args.test_all:
        prompts_to_test = []
        if args.test_prompt:
            prompts_to_test = [args.test_prompt]
        elif args.test_all and available_prompts:
            prompts_to_test = available_prompts
        
        if prompts_to_test:
            print("\n=== PROMPT TESTS ===")
            prompt_results = {}
            prompt_args = {}
            if args.prompt_args:
                try:
                    prompt_args = json.loads(args.prompt_args)
                except json.JSONDecodeError:
                    print(f"⚠️ Error parsing prompt args JSON: {args.prompt_args}")
                    prompt_args = {"description": "Test prompt"}
            else:
                # Default arguments for common prompts
                prompt_args = {"description": "Test prompt"}
            
            for prompt_name in prompts_to_test:
                success, message, content = await client.test_prompt(prompt_name, **prompt_args)
                prompt_results[prompt_name] = success
                if success:
                    print(f"✅ Prompt {prompt_name}: {message}")
                    if args.verbose:
                        print("Content:")
                        print(json.dumps(content, indent=2, ensure_ascii=False)[:500] + "..." if len(json.dumps(content)) > 500 else json.dumps(content, indent=2, ensure_ascii=False))
                else:
                    print(f"❌ Prompt {prompt_name}: {message}")
            test_results["prompts"] = prompt_results
            print()
    
    # Close the client
    await client.close()
    
    # Print test summary
    print("\n=== TEST SUMMARY ===")
    all_passed = True
    
    for test_name, result in test_results.items():
        if isinstance(result, dict):
            # For grouped tests like resources and prompts
            group_passed = all(result.values())
            all_passed = all_passed and group_passed
            if group_passed:
                print(f"✅ {test_name.capitalize()}: All passed")
            else:
                # Show which specific items failed
                print(f"❌ {test_name.capitalize()}: Some failed")
                for item, passed in result.items():
                    print(f"   {'✅' if passed else '❌'} {item}")
        else:
            # For simple tests
            all_passed = all_passed and result
            print(f"{'✅' if result else '❌'} {test_name.capitalize()}")
    
    if all_passed:
        print("\n✅ All tests passed! The MCP server is working correctly.")
    else:
        print("\n❌ Some tests failed. See details above for troubleshooting.")
    
    print("\nTests completed.")

if __name__ == "__main__":
    asyncio.run(main()) 