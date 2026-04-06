#!/usr/bin/env python3
"""
Automated setup script for Secure Vision
Checks dependencies, downloads models, and configures system
"""

import os
import sys
import subprocess
import platform

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def check_python_version():
    """Check if Python version is compatible"""
    print_header("Checking Python Version")
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 or higher required")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def install_dependencies():
    """Install required packages"""
    print_header("Installing Dependencies")
    
    try:
        print("Installing packages from requirements.txt...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False

def download_yolo_model():
    """Download YOLOv5 model"""
    print_header("Downloading YOLOv5 Model")
    
    try:
        import torch
        print("Downloading YOLOv5n model (this may take a few minutes)...")
        model = torch.hub.load('ultralytics/yolov5', 'yolov5n', pretrained=True)
        print("✅ YOLOv5 model downloaded successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to download YOLOv5: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    print_header("Creating Directories")
    
    directories = ['alerts', 'logs', 'models', 'data']
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Created directory: {directory}")
        except Exception as e:
            print(f"❌ Failed to create {directory}: {e}")
            return False
    
    return True

def setup_config():
    """Setup configuration file"""
    print_header("Setting Up Configuration")
    
    if os.path.exists('config.py'):
        print("⚠️  config.py already exists")
        response = input("Do you want to overwrite it? (y/n): ")
        if response.lower() != 'y':
            print("Skipping configuration setup")
            return True
    
    try:
        # Copy template to config.py
        with open('config_template.py', 'r') as template:
            content = template.read()
        
        with open('config.py', 'w') as config:
            config.write(content)
        
        print("✅ Configuration file created: config.py")
        print("⚠️  IMPORTANT: Edit config.py and add your API credentials!")
        return True
    except Exception as e:
        print(f"❌ Failed to create config: {e}")
        return False

def check_ml_model():
    """Check if ML model exists"""
    print_header("Checking ML Model")
    
    if os.path.exists('crash_prediction_model.pkl'):
        print("✅ ML model found: crash_prediction_model.pkl")
        return True
    else:
        print("⚠️  ML model not found: crash_prediction_model.pkl")
        print("   You need to train the model first using:")
        print("   - accident_detection.ipynb (Jupyter notebook)")
        print("   OR")
        print("   - python train_crash_model.py")
        return False

def check_camera():
    """Check if camera is available"""
    print_header("Checking Camera")
    
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret:
                print("✅ Camera detected and working")
                return True
            else:
                print("⚠️  Camera detected but not responding")
                return False
        else:
            print("⚠️  No camera detected")
            print("   You can still use video files for testing")
            return False
    except Exception as e:
        print(f"❌ Error checking camera: {e}")
        return False

def print_next_steps():
    """Print next steps for user"""
    print_header("Setup Complete!")
    
    print("Next Steps:")
    print("\n1. Configure your API credentials:")
    print("   - Edit config.py")
    print("   - Add Twilio credentials (for WhatsApp alerts)")
    print("   - Add Telegram bot token and chat ID")
    print("   - Update GPS coordinates")
    
    print("\n2. Train the ML model (if not done yet):")
    print("   - Open accident_detection.ipynb in Jupyter")
    print("   - Run all cells to train the model")
    
    print("\n3. Run the application:")
    print("   - python accident_detection_improved.py")
    
    print("\n4. Test emergency vehicle detection:")
    print("   - python emergency_vehicle_detection.py")
    
    print("\nDocumentation:")
    print("   - README.md: Complete documentation")
    print("   - BUG_FIXES.md: Bug fixes and improvements")
    print("   - config_template.py: Configuration reference")
    
    print("\n" + "=" * 60)
    print("Need help? Check README.md or create an issue on GitHub")
    print("=" * 60 + "\n")

def main():
    """Main setup function"""
    print("\n" + "🚨" * 20)
    print("  SECURE VISION - Automated Setup")
    print("🚨" * 20 + "\n")
    
    print("This script will:")
    print("  1. Check Python version")
    print("  2. Install dependencies")
    print("  3. Download YOLOv5 model")
    print("  4. Create necessary directories")
    print("  5. Setup configuration file")
    print("  6. Check ML model")
    print("  7. Check camera availability")
    
    input("\nPress Enter to continue...")
    
    # Run setup steps
    steps = [
        ("Python Version Check", check_python_version),
        ("Install Dependencies", install_dependencies),
        ("Download YOLOv5 Model", download_yolo_model),
        ("Create Directories", create_directories),
        ("Setup Configuration", setup_config),
        ("Check ML Model", check_ml_model),
        ("Check Camera", check_camera)
    ]
    
    results = {}
    for step_name, step_func in steps:
        results[step_name] = step_func()
    
    # Print summary
    print_header("Setup Summary")
    
    for step_name, result in results.items():
        status = "✅" if result else "⚠️"
        print(f"{status} {step_name}")
    
    # Print next steps
    print_next_steps()
    
    # Return overall success
    critical_steps = ["Python Version Check", "Install Dependencies", "Create Directories"]
    return all(results[step] for step in critical_steps)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)