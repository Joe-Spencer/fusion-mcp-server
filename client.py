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
    
    async def display_message(self, message: str) -> bool:
        """Display a message box in Fusion 360."""
        print(f"Displaying message: {message}")
        
        # First try using the tool
        result = await self.call_tool("message_box", message=message)
        if result:
            return True
        
        # If tool call failed, try the message file method
        message_file = COMM_DIR / "message_box.txt"
        with open(message_file, "w") as f:
            f.write(message)
        
        print(f"Created message file: {message_file}")
        
        # Wait to see if file gets processed
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            if not message_file.exists() or list(COMM_DIR.glob("processed_message_*.txt")):
                return True
            await asyncio.sleep(0.1)
        
        return False
    
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
    message_result = await client.display_message(f"MCP Test Message - {time.ctime()}")
    if message_result:
        print("✅ Message box displayed successfully")
    else:
        print("❌ Failed to display message box")
    
    return True

async def main():
    """Main entry point."""
    # First check for server status file which has the most detailed information
    status_file = COMM_DIR / "server_status.json"
    server_status = None
    
    if status_file.exists():
        try:
            with open(status_file, "r") as f:
                server_status = json.load(f)
            
            print(f"Found server status file:")
            print(f"  Status: {server_status.get('status', 'unknown')}")
            print(f"  Last updated: {server_status.get('formatted_time', 'unknown')}")
            print(f"  Server URL: {server_status.get('server_url', 'unknown')}")
            
            # If the server reports it's running, use its URL
            if server_status.get('status') == 'running' and server_status.get('server_url'):
                # Override the URL from command line if server has a different one
                if args.url != server_status.get('server_url'):
                    print(f"Updating URL from {args.url} to {server_status.get('server_url')}")
                    args.url = server_status.get('server_url')
        except Exception as e:
            print(f"Error reading server status file: {str(e)}")
    else:
        print("No server status file found. Checking ready files...")
        # Fall back to checking ready files
        ready_paths = [
            WORKSPACE_PATH / "mcp_server_ready.txt",
            WORKSPACE_PATH / "mcp_comm" / "mcp_server_ready.txt",
            Path(os.path.expanduser("~/Desktop/mcp_server_ready.txt")),
            Path("C:/Users/Joseph/AppData/Roaming/Autodesk/Autodesk Fusion 360/API/AddIns/MCPserve/mcp_comm/mcp_server_ready.txt")
        ]
        
        ready_files = []
        for path in ready_paths:
            if path.exists():
                try:
                    content = path.read_text().strip()
                    ready_files.append((path, content))
                except Exception as e:
                    ready_files.append((path, f"Error reading: {str(e)}"))
        
        if ready_files:
            print(f"Found {len(ready_files)} ready file(s):")
            for path, content in ready_files:
                print(f"  - {path}: {content}")
        else:
            print("No server ready files found. The MCP Server may not be running.")
            print("Please start the MCP Server command in Fusion 360 first.")
    
    # Check for any error logs
    error_file = COMM_DIR / "mcp_server_error.txt"
    if error_file.exists():
        try:
            error_content = error_file.read_text().strip()
            print("\n⚠️ Server error detected:")
            print(f"{error_content[:500]}..." if len(error_content) > 500 else error_content)
            print("\nThe server might not be functioning correctly.")
        except Exception as e:
            print(f"Error reading error file: {str(e)}")
    
    # Create client and run tests
    client = MCPClient(
        sse_url=args.url,
        timeout=args.timeout,
        use_sdk=args.use_sdk
    )
    
    try:
        success = await run_tests(client, server_status)
        if success:
            print("\n✅ All tests completed.")
        else:
            print("\n❌ Some tests failed.")
    finally:
        await client.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation canceled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1) 