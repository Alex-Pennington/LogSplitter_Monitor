# LogSplitter Complete Protobuf Implementation Plan

## Executive Summary

**Goal**: Fully implement the complete protobuf definition as received from the Arduino serial-to-MQTT bridge, ensuring 100% accurate decoding of all message types.

**Current Status**: ⚠️ **PARTIALLY FUNCTIONAL**
- 6/8 message types working with limitations
- SYSTEM_STATUS (0x16) CRITICAL FAILURE - no data for 7 days
- Most decoders using incorrect struct formats
- Missing enum name mappings and field validations

**Approach**: Test-driven development with unit testing for early success validation

---

## Problem Analysis

### Root Cause Identified
The `mqtt_protobuf_decoder.py` was written based on assumptions about the binary message format, but **never validated against the actual controller implementation**. The controller's `telemetry_manager.h` defines the authoritative binary structures, which differ significantly from what the decoder expects.

### Critical Mismatches Discovered

| Message Type | Expected Payload | Actual Payload | Decoder Format | Actual Format | Status |
|--------------|------------------|----------------|----------------|---------------|--------|
| DIGITAL_INPUT (0x10) | 4+ bytes | 3 bytes | `<BBH` (pin, flags, debounce_ms) | `<BBB` (pin, flags, debounce_low) | ⚠️ Works but incomplete |
| DIGITAL_OUTPUT (0x11) | 3+ bytes | 2 bytes | `<BB` (pin, flags) | `<BBB` (pin, flags, reserved) | ⚠️ Works but missing field |
| RELAY_EVENT (0x12) | 3+ bytes | 2 bytes | `<BB` (relay, flags) | `<BBB` (relay, flags, reserved) | ⚠️ Works but missing field |
| PRESSURE (0x13) | 9+ bytes | 7 bytes | `<BBHf` (pin, flags, raw, float) | `<BBHf` (same) | ✅ Matches! |
| SYSTEM_ERROR (0x14) | Variable | Not tested | Not implemented | `<BBB` + string | ❌ Not implemented |
| SAFETY_EVENT (0x15) | 3+ bytes | Not tested | Not implemented | `<BBB` (type, flags, reserved) | ❌ Not implemented |
| SYSTEM_STATUS (0x16) | 10+ bytes | 11 bytes | `<LHHB` (4 fields) | `<LHHBBH` (6 fields) | 🔴 CRITICAL - Wrong format |
| SEQUENCE_EVENT (0x17) | 3+ bytes | 3 bytes | `<BBH` (type, step, elapsed) | `<BBH` (same) | ✅ Likely matches |

### Impact Assessment

**CRITICAL (P0)**: SYSTEM_STATUS failure blocks all system health monitoring
- No uptime tracking
- No memory usage monitoring  
- No loop frequency metrics
- No active error counts
- No sequence state visibility

**HIGH (P1)**: Incomplete field decoding reduces telemetry value
- Missing input/output/relay type names
- Missing debounce times
- Missing reserved fields (future-proofing)
- No safety event tracking
- No system error reporting

**MEDIUM (P2)**: Data integrity concerns
- Corrupt pressure data in historical database
- Sequence gaps suggesting systematic decode failures
- No validation of field values

---

## Implementation Strategy

### Phase 1: Foundation (Tests First) ✅ EARLY SUCCESS

**Objective**: Create robust test framework before touching production code

**Tasks**:
1. **Unit Test Framework Setup** (ID 1)
   - Create `utils/tests/` directory structure
   - Install pytest: `pip install pytest pytest-cov`
   - Create `test_protobuf_decoder.py` with fixtures
   - Create binary message sample generator
   
2. **Binary Message Sample Capture** (ID 12)
   - Write `capture_protobuf_samples.py` to record live messages
   - Create `samples/` directory with known-good messages per type
   - Document each sample with hex dump and expected fields
   
3. **Test Data Generation** (ID 1 continued)
   - Create test fixtures with binary messages matching `telemetry_manager.h` structs
   - Generate edge cases: min/max values, zero fields, all flags set/unset
   - Add negative tests: truncated messages, invalid types, corrupt data

**Success Criteria**:
- ✅ pytest runs successfully (even if tests fail initially)
- ✅ Have 10+ binary message samples per message type
- ✅ Test framework can load samples and call decoder functions
- ✅ Test output clearly shows expected vs actual field values

**Early Win**: Test framework validates PRESSURE decoder (0x13) works correctly!

### Phase 2: Critical Fixes (Test-Driven) 🔴 HIGH PRIORITY

**Objective**: Fix SYSTEM_STATUS and complete core message decoders

**Tasks**:
4. **Fix SYSTEM_STATUS Decoder** (ID 2) - **HIGHEST PRIORITY**
   - Write unit test with binary sample: `18 16 XX XX XX XX XX LL LL HH HH MM MM EE FF RR RR`
   - Update `_decode_system_status()` to use `<LHHBBH` format:
     ```python
     uptime_ms, loop_freq, free_mem, error_count, flags, reserved = struct.unpack('<LHHBBH', payload[:12])
     ```
   - Add field mappings:
     - `safety_active = bool(flags & 0x01)`
     - `estop_active = bool(flags & 0x02)`
     - `sequence_state = (flags >> 2) & 0x0F` → map to SequenceState enum
     - `mill_lamp_pattern = (flags >> 6) & 0x03` → map to MillLampPattern enum
   - Run test: `pytest -v tests/test_protobuf_decoder.py::test_system_status`
   - **Success Metric**: Test passes, decode live SYSTEM_STATUS, see recent data in database

5. **Implement Complete DIGITAL_INPUT Decoder** (ID 3)
   - Write unit test with 3-byte payload: `10 10 XX XX XX XX XX PP FF DD`
   - Handle variable payload: 3 bytes (`<BBB`) or 4 bytes (`<BBH`)
   - Add `input_type_name` mapping from InputType enum
   - Run test: `pytest -v tests/test_protobuf_decoder.py::test_digital_input`

6. **Implement Complete RELAY_EVENT Decoder** (ID 5)
   - Write unit test with 3-byte payload: `09 12 XX XX XX XX XX RR FF 00`
   - Parse all fields: `relay_number`, `flags` → `state`, `is_manual`, `success`, `relay_type`
   - Add `relay_type_name` mapping from RelayType enum
   - Run test: `pytest -v tests/test_protobuf_decoder.py::test_relay_event`

7. **Verify PRESSURE Decoder** (ID 6)
   - Write comprehensive unit test with known pressure values
   - Test edge cases: 0 PSI, 5000 PSI, fault flag set
   - Validate float decoding accuracy
   - Run test: `pytest -v tests/test_protobuf_decoder.py::test_pressure`

**Success Criteria**:
- ✅ All 4 tests pass (SYSTEM_STATUS, DIGITAL_INPUT, RELAY_EVENT, PRESSURE)
- ✅ Live SYSTEM_STATUS messages decode successfully
- ✅ Database shows recent SYSTEM_STATUS records (last 5 minutes)
- ✅ No struct.unpack errors in service logs

**Early Win**: SYSTEM_STATUS working = immediate system health visibility restored!

### Phase 3: Complete Coverage 🔧 MEDIUM PRIORITY

**Objective**: Implement remaining message types and enum mappings

**Tasks**:
8. **Add Enum Name Mappings** (ID 10)
   - Create Python enums matching `telemetry_manager.h`:
     ```python
     class InputType(Enum):
         INPUT_UNKNOWN = 0
         INPUT_MANUAL_EXTEND = 1
         INPUT_MANUAL_RETRACT = 2
         # ... all 8 types
     
     class RelayType(Enum):
         RELAY_UNKNOWN = 0
         RELAY_HYDRAULIC_EXTEND = 1
         # ... all 9 types
     ```
   - Use `.name` for human-readable strings in decoded output
   - Write unit test: `pytest -v tests/test_enum_mappings.py`

9. **Implement SAFETY_EVENT Decoder** (ID 7)
   - Parse 3-byte payload: `event_type`, `flags` → `is_active`, `reserved`
   - Add safety event type enum and names
   - Write unit test with sample message
   - Run test: `pytest -v tests/test_protobuf_decoder.py::test_safety_event`

10. **Implement SYSTEM_ERROR Decoder** (ID 8)
    - Parse variable-length payload: `error_code(1) + flags(1) + desc_length(1) + description(0-24)`
    - Extract `severity` from flags: `(flags >> 2) & 0x03`
    - Map ErrorSeverity enum to names
    - Write unit test with sample error message
    - Run test: `pytest -v tests/test_protobuf_decoder.py::test_system_error`

11. **Complete DIGITAL_OUTPUT Decoder** (ID 4)
    - Update to parse 3-byte payload fully: `pin`, `flags`, `reserved`
    - Extract pattern from flags: `(flags >> 4) & 0x0F`
    - Add OutputType enum mapping
    - Write unit test
    - Run test: `pytest -v tests/test_protobuf_decoder.py::test_digital_output`

12. **Verify SEQUENCE_EVENT Decoder** (ID 9)
    - Write comprehensive unit test
    - Validate 4-byte payload parsing
    - Test elapsed_time_ms accuracy
    - Run test: `pytest -v tests/test_protobuf_decoder.py::test_sequence_event`

**Success Criteria**:
- ✅ All 8 message types (0x10-0x17) have complete decoders
- ✅ All enums mapped to human-readable names
- ✅ 100% test coverage for all decoders
- ✅ All tests passing: `pytest -v tests/`

### Phase 4: Infrastructure & Monitoring 📊 LOW PRIORITY

**Objective**: Production readiness with comprehensive monitoring

**Tasks**:
13. **Add Debug Logging** (ID 11)
    - Add `--debug` flag to `protobuf_database_logger.py`
    - Hexdump all failed decode attempts: `payload.hex()`
    - Log struct format used and expected payload size
    - Add to service: `ExecStart=/path/to/venv/bin/python protobuf_database_logger.py --debug`

14. **Update Database Schema** (ID 13)
    - Create migration script: `utils/migrate_telemetry_schema_v2.py`
    - Add columns for new fields:
      - `input_type_name TEXT`
      - `output_type_name TEXT`
      - `relay_type_name TEXT`
      - `loop_frequency_hz INTEGER`
      - `mill_lamp_pattern TEXT`
      - `error_severity TEXT`
      - `safety_event_type TEXT`
    - Run migration: `python migrate_telemetry_schema_v2.py`
    - Update `protobuf_database_logger.py` to insert new fields

15. **Create Integration Test** (ID 14)
    - Write `test_live_protobuf.py` to validate against running controller
    - Subscribe to `controller/protobuff` topic
    - Decode 100 messages of each type
    - Calculate decode success rate (target: 100%)
    - Report field validation errors
    - Run: `python test_live_protobuf.py --duration 300` (5 minutes)

16. **Update Web Dashboard** (ID 15)
    - Add API endpoint: `GET /api/system_status` (latest system health)
    - Add API endpoint: `GET /api/safety_events` (recent safety events)
    - Add API endpoint: `GET /api/system_errors` (active errors)
    - Add dashboard cards:
      - System Health (uptime, memory, loop frequency)
      - Safety Status (safety_active, estop_active, sequence_state)
      - Active Errors (error code, severity, description)
      - Relay History (with type names and manual/auto flag)
    - Update `dashboard.html` to fetch and display new data

17. **Add Protocol Documentation** (ID 16)
    - Create `PROTOBUF_PROTOCOL.md` with complete message format spec
    - Document each message type with hex examples
    - Include endianness, field order, flag bit masks
    - Add decoder implementation notes
    - Include troubleshooting guide for decode errors

**Success Criteria**:
- ✅ Service logs show decode success/failure clearly with hexdumps
- ✅ Database schema supports all telemetry fields
- ✅ Integration test reports 100% decode success
- ✅ Web dashboard shows all decoded telemetry data
- ✅ Documentation complete and accurate

### Phase 5: Validation & Cleanup 🎯 FINAL

**Objective**: End-to-end validation and data quality

**Tasks**:
18. **End-to-End Validation** (ID 17)
    - Run full test suite: `pytest -v --cov=mqtt_protobuf_decoder tests/`
    - Verify code coverage ≥90%
    - Run live integration test for 24 hours
    - Analyze service logs for any decode errors
    - Confirm all 8 message types in database with recent timestamps
    - Validate field value ranges (pressure 0-5000, memory >0, etc.)

19. **Clean Corrupt Data** (ID 18)
    - Write `clean_corrupt_data.py` to identify issues:
      - Pressure values outside 0-5000 PSI range
      - Negative memory values
      - Timestamps in future or too far past
      - NULL fields that should have values
    - Create backup: `cp logsplitter_data.db logsplitter_data.db.backup`
    - Run cleanup with dry-run mode
    - Execute cleanup and validate data integrity
    - Add database constraints to prevent future corruption

20. **Performance Validation**
    - Measure decode throughput (messages/second)
    - Verify MQTT publish rate ≤100/second (rate limit)
    - Check database write performance
    - Monitor service memory usage (should be stable <50MB)
    - Confirm no memory leaks over 24 hour run

**Success Criteria**:
- ✅ 100% test pass rate
- ✅ Code coverage ≥90%
- ✅ Zero decode errors in 24-hour live test
- ✅ All message types in database with fresh data (<5 minutes old)
- ✅ No corrupt data in database
- ✅ Service stable with <50MB memory usage

---

## Test-Driven Development Workflow

### Step-by-Step Process for Each Decoder

1. **RED: Write Failing Test First**
   ```bash
   # Create test with expected behavior
   $ cat tests/test_protobuf_decoder.py
   def test_system_status():
       # Binary message: size=18, type=0x16, seq=5, timestamp=12345678, payload=...
       message = bytes.fromhex('12 16 05 4E61BC00 CE290000 6400 1538 02 01 0000')
       result = decoder.decode_message(message)
       
       assert result['type'] == 0x16
       assert result['payload']['uptime_ms'] == 10702  # 0x29CE little-endian
       assert result['payload']['loop_frequency_hz'] == 100  # 0x64
       assert result['payload']['free_memory_bytes'] == 5398  # 0x1538
       assert result['payload']['active_error_count'] == 2
       assert result['payload']['safety_active'] == True  # flags & 0x01
       assert result['payload']['estop_active'] == False  # flags & 0x02
   
   # Run test - it will FAIL initially
   $ pytest -v tests/test_protobuf_decoder.py::test_system_status
   FAILED - AssertionError: struct.unpack requires a buffer of 10 bytes
   ```

2. **GREEN: Make Test Pass**
   ```python
   # Fix decoder in mqtt_protobuf_decoder.py
   def _decode_system_status(self, payload: bytes) -> Optional[Dict[str, Any]]:
       if len(payload) < 12:
           return None
       
       uptime, loop_freq, free_mem, err_count, flags, reserved = struct.unpack('<LHHBBH', payload[:12])
       
       return {
           'uptime_ms': uptime,
           'loop_frequency_hz': loop_freq,
           'free_memory_bytes': free_mem,
           'active_error_count': err_count,
           'safety_active': bool(flags & 0x01),
           'estop_active': bool(flags & 0x02),
           'sequence_state': (flags >> 2) & 0x0F,
           'mill_lamp_pattern': (flags >> 6) & 0x03
       }
   
   # Run test - it should PASS now
   $ pytest -v tests/test_protobuf_decoder.py::test_system_status
   PASSED
   ```

3. **REFACTOR: Improve Code Quality**
   - Add enum name mappings
   - Extract flag parsing to helper function
   - Add error handling for edge cases
   - Re-run tests to ensure still passing

4. **VALIDATE: Test with Live Data**
   ```bash
   # Restart service with fixed decoder
   $ ./logsplitter-services.sh restart logger
   
   # Watch logs for successful decode
   $ sudo journalctl -u logsplitter-protobuf-logger.service -f | grep "SYSTEM_STATUS"
   Nov 04 20:15:32 SYSTEM_STATUS uptime=12345 freq=102Hz mem=5234 errors=0
   
   # Query database for fresh data
   $ sqlite3 logsplitter_data.db "SELECT * FROM telemetry WHERE message_type=22 ORDER BY received_timestamp DESC LIMIT 1"
   2025-11-04 20:15:32|22|SYSTEM_STATUS|...
   ```

5. **CELEBRATE: Early Success! 🎉**
   - One more message type working
   - Progress visible immediately
   - Build confidence for next decoder

---

## Key Files and Locations

### Source Files
- **Controller**: `/home/rayvn/monitor/LogSplitter_Monitor/controller/LogSplitter_Controller-non-networking-version/include/telemetry_manager.h`
  - Authoritative binary message structure definitions
  - Enum definitions for all types
  - Payload size specifications

- **Decoder**: `/home/rayvn/monitor/LogSplitter_Monitor/utils/mqtt_protobuf_decoder.py`
  - Python decoder implementation
  - Message type handlers (0x10-0x17)
  - Struct format strings

- **Database Logger**: `/home/rayvn/monitor/LogSplitter_Monitor/utils/protobuf_database_logger.py`
  - MQTT subscriber
  - Database insertion logic
  - Service entry point

### Test Files (To Be Created)
- `utils/tests/test_protobuf_decoder.py` - Unit tests for all message types
- `utils/tests/test_enum_mappings.py` - Enum name mapping tests
- `utils/tests/conftest.py` - pytest fixtures and configuration
- `utils/tests/samples/` - Binary message samples per type

### Service Files
- `/etc/systemd/system/logsplitter-protobuf-logger.service` - systemd unit
- `/var/log/syslog` - Service logs (via journalctl)

### Database Files
- `/home/rayvn/monitor/LogSplitter_Monitor/utils/logsplitter_data.db` - SQLite database
- Schema: `telemetry` table with message type, timestamp, raw data, decoded fields

---

## Success Metrics

### Phase 1 (Foundation)
- [ ] pytest runs successfully with 0 tests (framework ready)
- [ ] Have 80+ binary message samples (10 per type × 8 types)
- [ ] Test fixtures load and validate samples correctly

### Phase 2 (Critical Fixes)
- [ ] SYSTEM_STATUS decoder test passes
- [ ] Live SYSTEM_STATUS messages appear in database (< 5 minutes old)
- [ ] Zero "unpack requires a buffer of X bytes" errors in logs
- [ ] DIGITAL_INPUT, RELAY_EVENT, PRESSURE decoders pass tests

### Phase 3 (Complete Coverage)
- [ ] All 8 message types have passing tests
- [ ] All enum mappings implemented and tested
- [ ] 100% test coverage for decoder functions
- [ ] Zero decode errors for any message type

### Phase 4 (Infrastructure)
- [ ] Debug logging shows hexdumps for all decode failures
- [ ] Database schema includes all telemetry fields
- [ ] Web dashboard displays all decoded data
- [ ] Integration test reports 100% success rate

### Phase 5 (Validation)
- [ ] 24-hour live test with zero errors
- [ ] All message types in database with fresh timestamps
- [ ] No corrupt data (all values in valid ranges)
- [ ] Service memory usage stable <50MB
- [ ] Documentation complete and accurate

---

## Risk Mitigation

### Risk 1: Controller Firmware Mismatch
**Scenario**: Controller may be running older/newer firmware with different message formats

**Mitigation**:
- Capture live binary samples from running controller
- Compare samples to `telemetry_manager.h` structs
- Add message format version field to header (future enhancement)
- Document any discovered firmware variations

### Risk 2: Incomplete Test Coverage
**Scenario**: Some message types may never occur in normal operation

**Mitigation**:
- Create synthetic binary messages for all types
- Use controller test commands to trigger all message types
- Monitor for 48+ hours to capture rare events (errors, safety)
- Add unit tests even if live samples unavailable

### Risk 3: Database Migration Failure
**Scenario**: Schema changes could corrupt existing data

**Mitigation**:
- **ALWAYS backup database before migration**: `cp logsplitter_data.db logsplitter_data.db.backup`
- Test migration on copy first: `cp logsplitter_data.db test.db && python migrate.py --db test.db`
- Make migrations reversible (keep old columns, add new ones)
- Validate data integrity after migration

### Risk 4: Service Downtime During Updates
**Scenario**: Updating decoder requires service restart, losing messages

**Mitigation**:
- Use MQTT broker message buffering (QoS 1)
- Keep service restarts under 5 seconds
- Schedule updates during low-activity periods
- Monitor message sequence gaps after restart

---

## Timeline Estimate

| Phase | Tasks | Estimated Time | Priority |
|-------|-------|---------------|----------|
| Phase 1: Foundation | 1-3 | 4 hours | P0 |
| Phase 2: Critical Fixes | 4-7 | 6 hours | P0 |
| Phase 3: Complete Coverage | 8-12 | 8 hours | P1 |
| Phase 4: Infrastructure | 13-17 | 6 hours | P2 |
| Phase 5: Validation | 18-20 | 4 hours | P2 |
| **TOTAL** | **20 tasks** | **28 hours** | |

**Aggressive Timeline**: 3-4 days with focused work
**Conservative Timeline**: 1-2 weeks with testing and validation

---

## Next Steps

1. **START HERE**: Run `manage_todo_list` to track progress
2. **Early Win**: Create test framework (Phase 1, Task 1)
3. **Critical Fix**: Fix SYSTEM_STATUS decoder (Phase 2, Task 4)
4. **Validate**: Test live SYSTEM_STATUS decode within 1 hour
5. **Iterate**: Work through remaining decoders with TDD workflow

**First Command**:
```bash
cd /home/rayvn/monitor/LogSplitter_Monitor/utils
mkdir -p tests/samples
pip install pytest pytest-cov
touch tests/__init__.py
touch tests/test_protobuf_decoder.py
pytest -v tests/  # Should run with 0 tests initially
```

---

## Conclusion

This plan provides a systematic, test-driven approach to fully implementing the LogSplitter protobuf telemetry system. By following the TDD workflow (RED → GREEN → REFACTOR → VALIDATE), we'll achieve:

✅ **Early Success**: Each test passing is immediate validation
✅ **High Confidence**: Comprehensive test coverage prevents regressions  
✅ **Clear Progress**: Todo list tracks completion of each decoder
✅ **Production Ready**: End-to-end validation ensures reliability

The critical SYSTEM_STATUS failure will be fixed in Phase 2 (6 hours), restoring system health monitoring. Complete implementation achieves 100% protocol coverage in ~28 hours.

**Let's start with Phase 1 and get that first test passing! 🚀**
