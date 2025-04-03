"""
MCP Installer for Fusion 360

This script helps install the MCP package for Fusion 360's Python environment.
It attempts to locate all Fusion 360 Python executables and install MCP for each one.
"""

import os
import sys
import subprocess
import glob
import winreg
import ctypes
from pathlib import Path

def is_admin():
    """Check if the script is running with admin privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def find_fusion_python_paths():
    """Find potential Fusion 360 Python paths"""
    paths = []
    
    # Try to find Fusion 360 install location from Windows registry
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
        for i in range(winreg.QueryInfoKey(key)[0]):
            try:
                subkey_name = winreg.EnumKey(key, i)
                subkey = winreg.OpenKey(key, subkey_name)
                try:
                    display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                    if "Fusion 360" in display_name:
                        install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                        paths.append(install_location)
                except:
                    pass
                winreg.CloseKey(subkey)
            except:
                continue
        winreg.CloseKey(key)
    except:
        pass
    
    # Common Fusion 360 install locations
    common_locations = [
        os.path.expanduser("~\\AppData\\Local\\Autodesk\\webdeploy"),
        "C:\\Program Files\\Autodesk\\webdeploy",
        "C:\\Program Files (x86)\\Autodesk\\webdeploy",
        os.path.expanduser("~\\AppData\\Local\\Autodesk\\Fusion 360")
    ]
    
    # Add common locations to search paths
    paths.extend(common_locations)
    
    # Look for Python executable in Fusion paths
    python_paths = []
    for base_path in paths:
        if os.path.exists(base_path):
            # Search for Python executable in production directories
            for prod_dir in glob.glob(os.path.join(base_path, "production", "*")):
                python_path = os.path.join(prod_dir, "Python", "python.exe")
                if os.path.exists(python_path):
                    python_paths.append(python_path)
            
            # Try common subdirectory patterns
            python_glob_patterns = [
                os.path.join(base_path, "*", "*", "Python", "python.exe"),
                os.path.join(base_path, "*", "Python", "python.exe"),
                os.path.join(base_path, "Python", "python.exe")
            ]
            
            for pattern in python_glob_patterns:
                for path in glob.glob(pattern):
                    if os.path.exists(path) and path not in python_paths:
                        python_paths.append(path)
    
    return python_paths

def install_mcp(python_path):
    """Install MCP using the specified Python executable"""
    try:
        print(f"\nAttempting to install MCP using: {python_path}")
        
        # Check if pip is available
        try:
            subprocess.run([python_path, "-m", "pip", "--version"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            print("Pip not available. Attempting to install pip first...")
            subprocess.run([python_path, "-m", "ensurepip", "--upgrade"], check=True)
        
        # Install MCP with CLI extras
        result = subprocess.run(
            [python_path, "-m", "pip", "install", "mcp[cli]"],
            capture_output=True,
            text=True,
            check=True
        )
        
        print("Installation output:")
        print(result.stdout)
        
        if result.stderr:
            print("Errors/Warnings:")
            print(result.stderr)
        
        # Verify installation - just check if we can import mcp without error
        verify = subprocess.run(
            [python_path, "-c", "import mcp; print('MCP installed successfully!')"],
            capture_output=True,
            text=True
        )
        
        if verify.returncode == 0:
            print("Verification output:")
            print(verify.stdout)
            return True
        else:
            print("Verification failed:")
            print(verify.stderr)
            return False
            
    except subprocess.CalledProcessError as e:
        print("Error during installation:")
        print(e.stdout)
        print(e.stderr)
        return False
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

def main():
    print("=== MCP Installer for Fusion 360 ===")
    print("This script will install the MCP package for ALL detected Fusion 360 Python environments.")
    
    # Check if we need admin privileges
    if not is_admin():
        print("Note: Some installation paths may require administrator privileges.")
        print("If installation fails, try running this script as administrator.")
    
    # Find Python paths
    print("\nSearching for Fusion 360 Python installations...")
    python_paths = find_fusion_python_paths()
    
    if not python_paths:
        print("No Fusion 360 Python installations found automatically.")
        custom_path = input("\nEnter the full path to Fusion 360's python.exe (or press Enter to exit): ")
        if custom_path and os.path.exists(custom_path):
            python_paths = [custom_path]
        else:
            if custom_path:
                print(f"Path does not exist: {custom_path}")
            print("\nExiting without installation.")
            return
    
    # Display found paths
    print(f"\nFound {len(python_paths)} potential Fusion 360 Python installation(s):")
    for i, path in enumerate(python_paths):
        print(f"{i+1}. {path}")
    
    # Ask for confirmation to install for all instances
    print(f"\nThis will install MCP with CLI extras for ALL {len(python_paths)} Python installations.")
    print("Using package specification: mcp[cli]")
    confirm = input("Proceed with installation for all installations? (y/n): ")
    
    if confirm.lower() != 'y':
        print("Installation cancelled.")
        return
    
    # Install MCP for all found Python installations
    successful_installs = 0
    failed_installs = 0
    
    for python_path in python_paths:
        success = install_mcp(python_path)
        if success:
            successful_installs += 1
            print(f"\n✓ Successfully installed MCP for: {python_path}")
        else:
            failed_installs += 1
            print(f"\n✗ Failed to install MCP for: {python_path}")
    
    # Final summary
    print("\n=== Installation Summary ===")
    print(f"Total Fusion 360 Python installations found: {len(python_paths)}")
    print(f"Successful installations: {successful_installs}")
    print(f"Failed installations: {failed_installs}")
    
    if successful_installs > 0:
        print("\nYou can now run the MCP Server Script in Fusion 360.")
    
    if failed_installs > 0:
        print("\nFor failed installations, you may need to try manually:")
        print("  1. Run this script as administrator")
        print("  2. Or install manually with: '[Python Path]' -m pip install \"mcp[cli]\"")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main() 