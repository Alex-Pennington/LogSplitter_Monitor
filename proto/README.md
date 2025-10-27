# LogSplitter Protocol Buffer Definitions

This directory contains the protobuf schema definitions for the LogSplitter system.

## Structure

When the protobuf definitions are uploaded, they will be organized as:

```
proto/
├── controller_messages.proto   # Main controller message definitions
├── sensor_data.proto          # Sensor reading message formats
├── system_status.proto        # System status and health messages
├── error_messages.proto       # Error and diagnostic messages
└── compiled/                  # Generated Python classes
    ├── __init__.py
    ├── controller_messages_pb2.py
    ├── sensor_data_pb2.py
    ├── system_status_pb2.py
    └── error_messages_pb2.py
```

## Compilation

To compile protobuf definitions to Python classes:

```bash
# From the proto directory
protoc --python_out=compiled/ *.proto
```

## Integration

The generated Python classes will be imported into the protobuf ingestion system for message parsing and processing.