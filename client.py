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
    
    # Check for server status file
    status_file = COMM_DIR / "server_status.json"
    if status_file.exists():
        try:
            with open(status_file, "r") as f:
                status = json.load(f)
                print("Found server status file:")
                print(f"  Status: {status.get('status', 'unknown')}")
                print(f"  Last updated: {status.get('started_at', 'unknown')}")
                print(f"  Server URL: {status.get('server_url', 'unknown')}")
                print()
        except Exception as e:
            print(f"Error reading server status file: {str(e)}")
    
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
    
    # Run selected tests
    any_test_selected = False
    
    # Test connection if requested or if no specific test is selected
    if args.test_connection or not any([
        args.test_message_box, args.list_resources, 
        args.list_tools, args.list_prompts
    ]):
        any_test_selected = True
        print("\nTesting connection to MCP server...")
        success, message = await client.test_connection()
        if success:
            print(f"✅ Connection successful: {message}")
        else:
            print(f"❌ Connection failed: {message}")
    
    # Check server status
    if status_file.exists():
        try:
            with open(status_file, "r") as f:
                status = json.load(f)
                print("\nUsing server status information from server_status.json file:\n")
                
                # List resources if requested
                if args.list_resources or not any_test_selected:
                    any_test_selected = True
                    resources = status.get("available_resources", [])
                    if resources:
                        print(f"Available resources:")
                        for resource in resources:
                            print(f"  - {resource}")
                        print()
                    else:
                        print("❌ No resources found in server status\n")
                
                # List tools if requested
                if args.list_tools or not any_test_selected:
                    any_test_selected = True
                    tools = status.get("available_tools", [])
                    if tools:
                        print(f"Available tools:")
                        for tool in tools:
                            print(f"  - {tool}")
                        print()
                    else:
                        print("❌ No tools found in server status\n")
                
                # List prompts if requested
                if args.list_prompts or not any_test_selected:
                    any_test_selected = True
                    prompts = status.get("available_prompts", [])
                    if prompts:
                        print(f"Available prompts:")
                        for prompt in prompts:
                            print(f"  - {prompt}")
                        print()
                    else:
                        print("❌ No prompts found in server status\n")
        except Exception as e:
            print(f"Error reading status file: {str(e)}")
    
    # Test message box if requested or if no specific test is selected
    if args.test_message_box or not any_test_selected:
        any_test_selected = True
        print("\n=== MESSAGE BOX TEST ===")
        print("⚠️ NOTE: Even if this test reports success, please verify that you actually see")
        print("a message box pop up in Fusion 360. This test can give false positives if the")
        print("server processes the command file but fails to display the actual message box.\n")
        
        message = args.message if args.message else None
        success, result = await client.test_message_box(message)
        if success:
            print(f"✅ Message box test appears successful: {result}")
            print("\n⚠️ IMPORTANT: Did you actually see a message box in Fusion 360?")
            print("If not, the server may not be functioning correctly despite this 'success' report.")
        else:
            print(f"❌ Message box test failed: {result}")
            print("\nCheck that Fusion 360 is running and the MCP Server add-in is active.")
            print("You can manually restart the MCP Server from the Add-Ins panel in Fusion 360.")
    
    # Close the client
    await client.close()
    
    print("\n✅ All tests completed.")

if __name__ == "__main__":
    asyncio.run(main()) 