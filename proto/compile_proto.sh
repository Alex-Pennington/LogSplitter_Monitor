#!/bin/bash

# LogSplitter Protobuf Compilation Script
# Compiles .proto files to Python classes

set -e

PROTO_DIR="/home/rayvn/monitor/LogSplitter_Monitor/proto"
COMPILED_DIR="$PROTO_DIR/compiled"

echo "LogSplitter Protobuf Compiler"
echo "============================="

# Create compiled directory if it doesn't exist
mkdir -p "$COMPILED_DIR"

# Check if protoc is installed
if ! command -v protoc &> /dev/null; then
    echo "Error: protoc (Protocol Buffer Compiler) is not installed"
    echo "Install with: sudo apt-get install protobuf-compiler"
    exit 1
fi

# Check if any .proto files exist
if ! ls "$PROTO_DIR"/*.proto 1> /dev/null 2>&1; then
    echo "No .proto files found in $PROTO_DIR"
    echo "Upload protobuf definitions first"
    exit 1
fi

echo "Compiling protobuf definitions..."
cd "$PROTO_DIR"

# Compile all .proto files
for proto_file in *.proto; do
    echo "Compiling $proto_file..."
    protoc --python_out=compiled/ "$proto_file"
done

# Create __init__.py for Python package
touch "$COMPILED_DIR/__init__.py"

echo "Compilation complete!"
echo "Generated Python classes in: $COMPILED_DIR"
echo ""
echo "Generated files:"
ls -la "$COMPILED_DIR"/*.py 2>/dev/null || echo "No Python files generated"