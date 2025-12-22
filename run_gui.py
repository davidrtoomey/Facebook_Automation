#!/usr/bin/env python3
"""
Marketplace Bot GUI Launcher
Builds React frontend and starts the FastAPI backend using uv
"""

import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path

def run_command(cmd, cwd=None, shell=False):
    """Run a command and return success status"""
    try:
        print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        result = subprocess.run(cmd, shell=shell, cwd=cwd, check=True, capture_output=True, text=True)
        print(f"✓ Command completed successfully")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"✗ Command failed with error: {e}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        return False, e.stderr

def check_node_installed():
    """Check if Node.js is installed"""
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Node.js found: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    
    print("✗ Node.js not found. Please install Node.js 16+ from https://nodejs.org/")
    return False

def check_uv_installed():
    """Check if uv is installed"""
    try:
        result = subprocess.run(['uv', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ uv found: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    
    print("✗ uv not found. Please install uv from https://github.com/astral-sh/uv")
    return False

def sync_dependencies():
    """Install GUI-specific dependencies"""
    print("\n📦 Installing GUI dependencies...")
    
    # Since we're in an existing environment, just install the GUI-specific packages
    gui_packages = [
        'fastapi==0.104.1',
        'uvicorn==0.24.0', 
        'python-multipart==0.0.6',
        'google-generativeai==0.3.1'
    ]
    
    for package in gui_packages:
        print(f"Installing {package}...")
        success, output = run_command(['uv', 'pip', 'install', package])
        if not success:
            print(f"Warning: Failed to install {package}, trying with pip...")
            success, output = run_command([sys.executable, '-m', 'pip', 'install', package])
            if not success:
                print(f"✗ Failed to install {package}")
                return False
    
    print("✓ GUI dependencies installed successfully")
    return True

def build_frontend():
    """Build the React frontend"""
    print("\n🔨 Building React frontend...")
    
    frontend_dir = Path(__file__).parent / "gui" / "frontend"
    if not frontend_dir.exists():
        print("✗ Frontend directory not found")
        return False
    
    # Install dependencies
    print("📦 Installing npm dependencies...")
    success, output = run_command(["npm", "install"], cwd=frontend_dir)
    if not success:
        print("✗ Failed to install npm dependencies")
        return False
    
    # Build the React app
    print("🏗️  Building React app...")
    success, output = run_command(["npm", "run", "build"], cwd=frontend_dir)
    if not success:
        print("✗ Failed to build React app")
        return False
    
    # Copy build files to backend static directory
    build_dir = frontend_dir / "build"
    backend_dir = Path(__file__).parent / "gui" / "backend"
    static_dir = backend_dir / "static"
    
    if build_dir.exists():
        print("📁 Copying build files to backend...")
        
        # Remove existing static directory
        if static_dir.exists():
            import shutil
            shutil.rmtree(static_dir)
        
        # Copy build directory to static
        import shutil
        shutil.copytree(build_dir, static_dir)
        
        print("✓ Frontend build completed successfully")
        return True
    else:
        print("✗ Build directory not found")
        return False

def start_backend():
    """Start the FastAPI backend"""
    print("\n🚀 Starting Marketplace Bot GUI...")

    backend_dir = Path(__file__).parent / "gui" / "backend"
    main_file = backend_dir / "main.py"

    if main_file.exists():
        print("🌐 Backend will be available at: http://localhost:8000")
        print("📱 React frontend will be served from: http://localhost:8000")
        print("🔌 WebSocket endpoint: ws://localhost:8000/ws/{client_id}")
        print("\n💡 The browser will open automatically in a few seconds...")
        print("🛑 Press Ctrl+C to stop the server\n")

        # Use uv to run the backend - don't capture output, let it run in foreground
        try:
            subprocess.run([
                'uv', 'run', 'python', str(main_file)
            ], check=True)
        except KeyboardInterrupt:
            print("\n🛑 Server stopped by user")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to start backend: {e}")
            return False

    else:
        print("✗ main.py not found in gui/backend directory")
        return False

def main():
    """Main launcher function"""
    print("🤖 Marketplace Bot GUI Launcher")
    print("=" * 50)
    
    # Check prerequisites
    print("\n🔍 Checking prerequisites...")
    
    if not check_uv_installed():
        return False
    
    if not check_node_installed():
        return False
    
    # Install GUI dependencies
    if not sync_dependencies():
        return False
    
    # Build frontend
    if not build_frontend():
        return False
    
    # Start backend
    print("\n✅ All checks passed! Starting the application...")
    start_backend()
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Application stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)