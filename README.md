# Fusion 360 MCP Server

This repository contains a Model Context Protocol (MCP) server for Autodesk Fusion 360. It enables AI assistants like Claude to interact directly with Fusion 360 using the MCP protocol.

## Overview

The server is implemented as a Fusion 360 add-in that exposes Fusion 360's functionality through MCP. This allows AI agents to:

1. Access information about the current design
2. Create and modify design elements 
3. Receive context-specific prompts for CAD tasks

The repository includes:

1. `MCPserve/` - The Fusion 360 add-in that implements the MCP server
2. `client.py` - A testing utility to verify server functionality
3. `install_mcp_for_fusion.py` - A helper script to install the MCP package for Fusion 360's Python environment

## How It Works

The MCP server runs within Fusion 360 and exposes a communication channel that AI agents can use to:

1. **Access resources** - Get information about the current design, components, parameters, etc.
2. **Use tools** - Perform actions like creating sketches, adding parameters, or displaying messages
3. **Get prompts** - Receive specialized prompt templates for CAD-related tasks

## Requirements

- Autodesk Fusion 360
- Python 3.7+ (for installation and testing)
- MCP Python SDK: `pip install "mcp[cli]"` (must be installed in Fusion 360's Python environment)

## Installation

### 1. Install MCP in Fusion 360's Python Environment

Fusion 360 uses its own Python environment, separate from your system's Python. The MCP package must be installed there.

**Using the Installer Script (Recommended):**

```bash
python install_mcp_for_fusion.py
```

This script will:
1. Find all Fusion 360 Python installations on your system
2. Install the MCP package with CLI extras for each installation
3. Verify the installation was successful

**Manual Installation:**

If the installer script doesn't work, you can manually install the package:

1. Find Fusion 360's Python executable (usually in `Autodesk\webdeploy\production\[version]\Python`)
2. Install the package:
   ```bash
   "[Fusion Python Path]\python.exe" -m pip install "mcp[cli]"
   ```

### 2. Install the Fusion 360 Add-in

1. In Fusion 360, click on "Tools" tab → "Add-Ins" → "Scripts and Add-Ins"
2. Click the green "+" button in the "My Add-Ins" tab
3. Browse to and select the `MCPserve` folder from this repository
4. Click "Open" to add it to your add-ins
5. Select it and click "Run" to start it

## Using the MCP Server with AI Assistants

The server enables AI assistants like Claude to interact with Fusion 360 in several ways:

### Resources

AI assistants can access these resources:

- `fusion://active-document-info` - Basic information about the active document
- `fusion://design-structure` - Detailed structure of the current design
- `fusion://parameters` - User parameters defined in the document

### Tools

AI assistants can use these tools:

- `message_box` - Display a message box in Fusion 360
- `create_new_sketch` - Create a new sketch on a specified plane
- `create_parameter` - Create a new parameter with specified values

### Prompts

AI assistants can use specialized prompts:

- `create_sketch_prompt` - Expert guidance for creating sketches
- `parameter_setup_prompt` - Expert guidance for setting up parameters

## Testing the Server

Use the included client script to test if the server is functioning correctly:

```bash
python client.py --test-connection
```

To test specific functionality:

```bash
# Test displaying a message box
python client.py --test-message-box

# Test listing available resources
python client.py --list-resources

# Test listing available tools
python client.py --list-tools

# Test listing available prompts
python client.py --list-prompts
```

## Communication Methods

The MCP server supports two methods of communication:

1. **MCP Protocol over HTTP SSE** - The standard MCP protocol implementation, accessible at `http://127.0.0.1:3000/sse`
2. **File-based Communication** - A backup method using files in the `mcp_comm` directory for environments that can't directly connect to the HTTP endpoint

## Technical Details

The server implementation:

1. Runs as a background thread in Fusion 360 to maintain responsiveness
2. Automatically creates ready files to signal when it's available
3. Registers resources, tools, and prompts with the MCP protocol
4. Monitors for file-based commands when HTTP communication isn't possible

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol/python-sdk) for the Python SDK
- Autodesk Fusion 360 for the powerful CAD/CAM platform
