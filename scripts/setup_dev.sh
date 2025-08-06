#!/bin/bash
# Development environment setup script for Haptic Feedback Vest

set -e

echo "Setting up Haptic Feedback Vest development environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Install development dependencies
echo "Installing development dependencies..."
pip install -e ".[dev]"

# Create necessary directories
echo "Creating project directories..."
mkdir -p logs
mkdir -p assets/test_images
mkdir -p models

# Set up pre-commit hooks (if available)
if command -v pre-commit &> /dev/null; then
    echo "Setting up pre-commit hooks..."
    pre-commit install
fi

echo "Development environment setup complete!"
echo ""
echo "To activate the environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To run the application in development mode:"
echo "  make run-dev"
echo ""
echo "To run tests:"
echo "  make test"
echo ""
echo "For more commands, run:"
echo "  make help"
