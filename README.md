# Fusion 360 MCP Server

This repository contains a Model Context Protocol (MCP) server for Autodesk Fusion 360. It allows AI assistants to interact with Fusion 360 using the MCP protocol.

## Overview

The server is implemented as a Fusion 360 add-in that makes Fusion 360's functionality available through MCP. The repository includes:

1. `MCPserve/` - The main Fusion 360 add-in that implements the MCP server
2. `MCP Server Script/MCP Server Script.py` - A script version of the MCP server (for backwards compatibility)
3. `client.py` - A simple client for testing the server
4. `install_mcp_for_fusion.py` - A helper script to install the MCP package for Fusion 360's Python environment

## Requirements

- Autodesk Fusion 360
- Python 3.7+ (for the client and installer)
- MCP Python SDK with CLI extras: `pip install "mcp[cli]"`

## Installation

### Installing MCP for Fusion 360

Fusion 360 uses its own Python environment, which is separate from your system's Python. The MCP package needs to be installed in Fusion 360's Python environment.

#### Option 1: Using the Installer Script (Recommended)

The easiest way to install MCP is to use the provided installer script:

```bash
python install_mcp_for_fusion.py
```

This script will:
1. Locate all Fusion 360 Python installations on your system
2. Install the MCP package with CLI extras for each installation
3. Verify that the installation was successful

#### Option 2: Manual Installation

If the installer script doesn't work, you can manually install the MCP package:

1. Find the Python executable used by Fusion 360:
   - Usually located in `Autodesk\webdeploy\production\[version]\Python`

2. Install MCP with CLI extras:
   ```bash
   "[Fusion Python Path]\python.exe" -m pip install "mcp[cli]"
   ```

   Note: The quotes around `"mcp[cli]"` are important to prevent shell expansion of the square brackets.

### Troubleshooting

If you encounter an error like "No module named 'mcp'", it means that the MCP package is not installed in Fusion 360's Python environment. Try using the installer script or manually installing the package.

## Usage

### Installing the Add-in (Recommended Method)

To use the MCP server, you should install it as a Fusion 360 add-in:

1. In Fusion 360, click on the "Tools" tab, then select "Add-Ins" > "Scripts and Add-Ins"
2. In the dialog that appears, click the green "+" button in the "My Add-Ins" tab
3. Browse to and select the `MCPserve` folder from this repository
4. Click "Open" to add it to your add-ins
5. The add-in should now appear in your list. Select it and click "Run" to start it

Once installed, the add-in will:
1. Automatically start when Fusion 360 starts (due to the `runOnStartup` setting in the manifest)
2. Create a command in the Add-Ins panel that you can use to start/restart the server if needed
3. Create a ready file to signal that the server is running

### Using the Script Version (Alternative Method)

If you prefer to use the script version instead of the add-in:

1. In Fusion 360, navigate to the **Scripts and Add-ins** dialog (Shift+S)
2. Click the green plus icon to add the script
3. Browse to and select `MCP Server Script/MCP Server Script.py`
4. Run the script

The server will start and be ready to handle client connections. A message box will appear when the server is ready, and a ready file (`mcp_server_ready.txt`) will be created to indicate that the server is running.

Note: The script version will only run temporarily and does not stay active in the background like the add-in version.

### Running the Client

The client is a simple script that tests the server functionality:

```bash
python client.py
```

This will:
1. Wait for the server to be ready
2. Run tests to verify that the server is functioning correctly

To test the message box functionality specifically:

```bash
python client.py --test-message-box
```

This will create a message file that the server will detect and display as a message box in Fusion 360.

## Server Implementation

The server implementation:

1. Sets up resources, tools, and prompts in-memory
2. Creates a ready file to signal that the server is running
3. Runs in a background thread to prevent blocking Fusion 360's UI
4. Remains active as a Fusion 360 add-in to ensure it doesn't terminate

## Resources

The server provides several resources:

- `active-document-info` - Information about the active document
- `design-structure` - Structure of the active design
- `parameters` - User parameters defined in the document

## Tools

The server provides several tools:

- `message_box` - Display a message box in Fusion 360
- `create_new_sketch` - Create a new sketch on a specified plane
- `create_parameter` - Create a new user parameter

## Prompts

The server provides prompts that can be used by AI assistants:

- `create_sketch_prompt` - Prompt for setting up a new sketch
- `parameter_setup_prompt` - Prompt for setting up parameters

## Differences Between Add-in and Script Versions

The MCPserve add-in has several advantages over the script version:

1. **Persistence**: The add-in stays running in the background even after Fusion 360 completes other operations
2. **Automatic Start**: The add-in can be configured to start automatically when Fusion 360 launches
3. **UI Integration**: The add-in adds a button to the Fusion 360 interface for easy access
4. **Proper Lifecycle**: The add-in follows proper add-in practices with start/stop lifecycle management

The script version is simpler but will terminate after execution, which may not be ideal for long-running MCP server functionality.

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol/python-sdk) for the Python SDK
- Autodesk Fusion 360 for the powerful CAD/CAM platform
