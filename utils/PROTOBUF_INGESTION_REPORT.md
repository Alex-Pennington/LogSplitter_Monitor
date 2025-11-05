# LogSplitter Protobuf Ingestion Status Report
**Date**: November 4, 2025, 2:30 PM EST  
**Investigator**: AI Assistant  
**System**: LogSplitter Controller → Monitor Protobuf Pipeline

## Executive Summary

**STATUS**: ⚠️ PARTIALLY FUNCTIONAL - Critical Issues Found

The protobuf ingestion system is operational but experiencing significant data loss and decode errors. Only a subset of message types are being successfully ingested, with SYSTEM_STATUS messages completely absent since October 28, 2025.

---

## Findings

### 1. Message Ingestion Status

#### ✅ Successfully Ingested (Recent Data)
| Message Type | Type ID | Count | Last Seen | Status |
|--------------|---------|-------|-----------|--------|
| DIGITAL_OUTPUT | 0x11 | 19,437 | Nov 4, 18:49 | ✅ Working |
| PRESSURE | 0x13 | 5,358 | Nov 4, 19:31 | ✅ Working |
| DIGITAL_INPUT | 0x10 | 1,974 | Nov 4, 18:56 | ✅ Working |
| SEQUENCE_EVENT | 0x17 | 1,911 | Nov 4, 18:56 | ✅ Working |
| RELAY_EVENT | 0x12 | 1,072 | Nov 4, 18:56 | ✅ Working |
| SENSOR_CALIBRATION | 0x0A | 692 | Nov 4, 18:56 | ✅ Working |

#### ❌ NOT Being Ingested (Stale or Missing Data)
| Message Type | Type ID | Count | Last Seen | Issue |
|--------------|---------|-------|-----------|-------|
| **SYSTEM_STATUS** | **0x16** | 408 | **Oct 28, 19:29** | 🚨 **CRITICAL: No data for 7 days** |

#### ⚠️ Unknown/Garbage Messages
Multiple unknown message types are being received, indicating:
- Corrupt messages
- Undocumented message types
- Decode errors creating false message types

**Examples**: 0x02, 0x04, 0x06, 0x07, 0x1A, 0x1D, 0xE6, 0xF3, 0xB4, 0xBA

---

### 2. Active Decode Errors

**Error Pattern** (Occurring every 10-30 seconds):
```
WARNING: Sequence gap for type 0x16: expected X, got Y
ERROR: Decode exception: unpack requires a buffer of 10 bytes
```

**Analysis**:
- Message type 0x16 (SYSTEM_STATUS) is being received
- Decoder is failing to extract the payload
- Sequence gaps indicate messages are being dropped/corrupted
- Error suggests payload is smaller than expected (< 10 bytes)

**Impact**: 
- SYSTEM_STATUS messages are received but FAIL to decode
- No system health data (uptime, memory, loop frequency, errors)
- Analytics dashboard "System Health" card has NO DATA

---

### 3. Message Structure Analysis

**Observed Structure** (from successfully ingested messages):
```
Total Size: 9-18 bytes
├── Byte 0: Size byte (total message length)
├── Byte 1: Message type (0x10-0x17)
├── Byte 2: Sequence number (0-255)
├── Bytes 3-6: Timestamp (uint32, little-endian, milliseconds)
└── Bytes 7+: Payload (variable length)
```

**Payload Sizes** (actual vs expected):
| Message Type | Expected | Actual | Status |
|--------------|----------|--------|--------|
| DIGITAL_INPUT | 4+ bytes | 3 bytes | ⚠️ Short |
| DIGITAL_OUTPUT | 3+ bytes | 2 bytes | ⚠️ Short |
| RELAY_EVENT | 3+ bytes | 2 bytes | ⚠️ Short |
| PRESSURE | 9+ bytes | 7 bytes | ⚠️ Short |
| SYSTEM_STATUS | 10+ bytes | 11 bytes | ✅ Adequate (but failing) |
| SEQUENCE_EVENT | 3+ bytes | 3 bytes | ✅ Adequate |

**Key Observation**: Most messages have SHORTER payloads than expected by the protobuf specification, but they're still being decoded successfully. SYSTEM_STATUS has adequate payload but fails uniquely.

---

### 4. Sequence Gap Analysis

**Pattern**: Every ~10 seconds, sequence gaps occur for type 0x16
```
Expected: 123 → Got: 129 (gap of 6)
Expected: 130 → Got: 136 (gap of 6)  
Expected: 137 → Got: 143 (gap of 6)
```

**Interpretation**:
- Controller IS sending SYSTEM_STATUS messages (type 0x16)
- Approximately 6 messages are being lost/corrupted per batch
- Pattern is consistent (always ~6 message gap)
- Suggests systematic decode failure, not transmission issue

---

### 5. Monitor Data (MQTT Topics)

**Successfully Ingesting**:
- `monitor/weight`: Weight sensor data (fuel tank)
- `monitor/temperature`: Temperature readings
- `monitor/uptime`: Monitor uptime
- `monitor/memory`: Monitor memory usage

**Status**: ✅ Monitor data is working correctly (non-protobuf MQTT messages)

---

## Root Cause Analysis

### Primary Issue: SYSTEM_STATUS Decode Failure

**Hypothesis**: Decoder expects different payload structure than controller is sending

**Evidence**:
1. Message arrives with 11-byte payload (adequate size)
2. Decoder function requires minimum 10 bytes
3. Decode fails with "unpack requires a buffer of 10 bytes"
4. Other message types decode successfully despite short payloads

**Likely Causes**:
1. **Struct format mismatch**: Decoder `struct.unpack('<LHHB', payload[:10])` may not match actual binary layout
2. **Endianness issue**: Little-endian assumption may be incorrect
3. **Alignment/padding**: Compiler padding in Arduino struct vs Python unpacking
4. **Version mismatch**: Controller firmware updated without decoder update

### Secondary Issue: Payload Size Discrepancies

Most messages have shorter payloads than protobuf spec defines, but decode successfully. This suggests:
- Decoder has fallback logic for shorter messages
- Optional fields are not being sent
- Specification is more generous than implementation

---

## Impact Assessment

### Critical (Production-Blocking)
- ❌ **System Health Monitoring**: No system status data for analytics
- ❌ **Performance Metrics**: No loop frequency, memory usage data
- ❌ **Error Detection**: No active error count monitoring

### High (Functionality Loss)
- ⚠️ **Sequence Gaps**: ~6 messages per batch being lost (could be other types too)
- ⚠️ **Unknown Messages**: Garbage data cluttering database

### Medium (Operational Concerns)
- ⚠️ **Data Integrity**: 7-day gap in SYSTEM_STATUS suggests recent issue
- ⚠️ **Historical Data**: Limited SYSTEM_STATUS history (Oct 27-28 only)

### Low (Working as Expected)
- ✅ **Core Telemetry**: PRESSURE, RELAY_EVENT, SEQUENCE_EVENT working
- ✅ **Monitor Data**: Weight, temperature, uptime working
- ✅ **Database Storage**: Messages being stored correctly when decoded

---

## Recommendations

### Immediate Actions (Priority 1)
1. **Fix SYSTEM_STATUS Decoder**
   - Add debug logging to see exact binary payload
   - Compare controller C struct with Python struct.unpack format
   - Add exception handling with hexdump on failure
   
2. **Investigate Sequence Gaps**
   - Determine if gaps are SYSTEM_STATUS only or affecting other types
   - Check if controller is actually sending those sequence numbers
   
3. **Monitor Live Decode**
   - Tail the protobuf logger with verbose output
   - Capture raw MQTT messages for analysis

### Short Term (Priority 2)
4. **Payload Size Audit**
   - Document actual vs expected payload sizes for all types
   - Update decoder to handle actual sizes gracefully
   
5. **Unknown Message Handling**
   - Filter out garbage messages (0x02, 0x04, etc.)
   - Log unknowns separately for analysis
   
6. **Error Metrics**
   - Track decode success/failure rates per message type
   - Alert on sustained decode failures

### Long Term (Priority 3)
7. **Protocol Versioning**
   - Add version field to messages
   - Support multiple protocol versions in decoder
   
8. **Validation Layer**
   - CRC or checksum on messages
   - Validate message structure before decode
   
9. **Integration Testing**
   - Automated tests comparing controller output to decoder input
   - Regression tests for each message type

---

## Current System Health

### Protobuf Logger Service
- **Status**: ✅ Running (PID 1271, started Nov 4 10:05:14)
- **Uptime**: 4+ hours
- **Memory**: 32.3 MB
- **CPU**: 15.576s total
- **Messages Received**: Thousands (exact count not logged)
- **Decode Errors**: Occurring every 10-30 seconds

### Database
- **Total Messages**: 30,000+ telemetry records
- **Database Size**: 4.3 MB (logsplitter_data.db)
- **Oldest Record**: Oct 27, 2025
- **Newest Record**: Nov 4, 2025 (ongoing)

### Web Dashboard
- **Status**: ✅ Running and accessible
- **Analytics**: Partially functional (missing system health data)
- **Real-time Updates**: Working for available data types

---

## Conclusion

The protobuf ingestion system was **never fully functional** for all message types. While core telemetry (pressure, relays, sequences) works reliably, SYSTEM_STATUS has been problematic since inception. The October 28 cutoff indicates either:
1. Controller stopped sending SYSTEM_STATUS messages
2. A decoder change broke SYSTEM_STATUS parsing
3. Message format changed without decoder update

**Verdict**: ⚠️ System is operational for monitoring hydraulic operations but lacks system health telemetry. Immediate investigation and fix required for SYSTEM_STATUS decoding.

---

## Next Steps

**Recommended Immediate Action**:
```bash
# Enable verbose debugging
sudo journalctl -u logsplitter-protobuf-logger.service -f

# Capture raw MQTT messages
mosquitto_sub -h 159.203.138.46 -p 1883 -u rayven -P [password] -t controller/protobuff | xxd

# Compare controller struct definition to decoder
# Check controller/src/ for SYSTEM_STATUS message packing code
```

**Questions to Answer**:
1. Is the controller still sending SYSTEM_STATUS messages?
2. What is the exact binary format of a SYSTEM_STATUS message?
3. When did SYSTEM_STATUS ingestion stop working (Oct 28)?
4. Are there other message types silently failing?

---

**Report Generated**: 2025-11-04 14:30:00 EST  
**Investigation Time**: 30 minutes  
**Data Sources**: logsplitter_data.db, systemd journals, MQTT logs
