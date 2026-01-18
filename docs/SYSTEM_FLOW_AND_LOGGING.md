# FlexTraff System Architecture & Data Flow Documentation

**Last Updated:** January 18, 2026

---

## 📋 Overview

This documentation outlines the complete data flow, logging system, and monitoring capabilities of the FlexTraff Adaptive Traffic Control System (ATCS). The system receives real-time traffic data from Raspberry Pi RFID scanners via MQTT, processes it, and logs everything for user visibility and system management.

---

## 🏗️ System Architecture

### Components

1. **Raspberry Pi (Edge Device)**
   - Captures vehicle counts from RFID scanners
   - Publishes data via MQTT
   - Receives calculated green times for traffic light control

2. **MQTT Broker** (HiveMQ Public Broker)
   - Handles message publishing and subscription
   - Topics: `flextraff/car_counts` and `flextraff/green_times`

3. **FlexTraff Backend (FastAPI)**
   - Receives MQTT messages
   - Logs data to Supabase
   - Calculates optimal traffic timings
   - Manages system events and errors

4. **Supabase (Database)**
   - Stores traffic data
   - Logs system events
   - Tracks scanner data

5. **Frontend (React)**
   - Displays logs and real-time data
   - Shows system status and health
   - Allows user management and monitoring

---

## 📡 Data Flow

### 1. **Vehicle Count Data Reception (MQTT → Backend)**

**Topic:** `flextraff/car_counts`

**Expected Payload Format:**
```json
{
  "lane_counts": [5, 3, 8, 4],
  "cycle_id": 123,
  "junction_id": 1
}
```

**Field Descriptions:**
- `lane_counts` (array): Vehicle counts for [North, South, East, West] lanes
- `cycle_id`: Unique identifier for this traffic cycle
- `junction_id`: Which junction/intersection is sending data

**Processing Steps:**
1. ✅ Backend receives MQTT message
2. ✅ Validates JSON format
3. ✅ **Logs RFID Scanner Data** → `rfid_scanners` table
4. ✅ Calls traffic calculation algorithm
5. ✅ Publishes green times back to Raspberry Pi

---

### 2. **RFID Scanner Logging (New Feature)**

**Table:** `rfid_scanners`

**New Columns Added:**
- `lane_car_count` (JSONB): Stores car counts with named lanes
  ```json
  {
    "north": 5,
    "south": 3,
    "east": 8,
    "west": 4
  }
  ```
- `cycle_id` (bigint): Links to the `traffic_cycles` table
- `log_timestamp` (timestamp): When the scanner recorded this data

**Example Database Entry:**
```
id: 42
junction_id: 1
lane_car_count: {"north": 5, "south": 3, "east": 8, "west": 4}
cycle_id: 123
log_timestamp: 2026-01-18 14:32:45.123Z
```

**Purpose:**
- Provides audit trail of traffic data
- Shows user vehicle count history
- Links traffic data with specific cycles
- Enables analysis and reporting

---

### 3. **Traffic Cycle Calculation**

**Process:**
1. Backend receives lane counts
2. Traffic Calculator algorithm determines optimal green times
3. Results stored in `traffic_cycles` table
4. Green times published back to MQTT

**Published Response:**
```json
{
  "green_times": [45, 30, 40, 35],
  "cycle_time": 120,
  "junction_id": 1,
  "cycle_id": 123
}
```

---

### 4. **System Logging & Error Handling (Enhanced)**

**Table:** `system_logs`

**Log Entries Include:**
- **Component:** Which part of the system generated the log
- **Log Level:** INFO, ERROR, WARNING
- **Message:** Detailed description
- **Metadata:** Additional context (JSON)
- **Timestamp:** When the event occurred
- **Junction ID:** Which junction it relates to

**Log Types:**

#### ✅ **System Start Log**
```
Component: startup
Level: INFO
Message: FlexTraff backend started successfully
```

#### ❌ **System Error Logs**

**Example 1: MQTT Connection Error**
```
Component: mqtt_handler
Level: ERROR
Message: MQTT_HANDLER_ERROR: Connection timeout
Timestamp: 2026-01-18 14:35:22Z
```

**Example 2: Database Error**
```
Component: rfid_scanner
Level: ERROR
Message: RFID_LOGGING_ERROR: Database insert failed
Metadata: {"cycle_id": 123, "junction_id": 1}
```

**Example 3: FastAPI Communication Error**
```
Component: mqtt_handler
Level: ERROR
Message: FASTAPI_TIMEOUT: FastAPI request timed out after 30 seconds
Junction ID: 1
```

#### ℹ️ **Informational Logs**
```
Component: rfid_scanner
Level: INFO
Message: RFID scanner log created | cycle_id=123 | counts={"north": 5, ...}
```

---

## 🚨 Error Handling & System Crash Logging

### Error Types Tracked

| Error Type | Component | Trigger | Example |
|-----------|-----------|---------|---------|
| **MQTT_HANDLER_ERROR** | mqtt_handler | Unhandled exception in MQTT handler | JSON parsing fails |
| **RFID_LOGGING_ERROR** | rfid_scanner | Failed to log RFID data | Database insert fails |
| **FASTAPI_TIMEOUT** | mqtt_handler | API request exceeds 30s | Backend is slow |
| **FASTAPI_CONNECT_ERROR** | mqtt_handler | Cannot reach backend API | Backend is offline |
| **JSON_DECODE_ERROR** | mqtt_handler | Invalid JSON from Raspberry Pi | Malformed message |
| **MQTT_SUBSCRIPTION_ERROR** | mqtt_startup | Failed to subscribe to topic | Broker connection issue |
| **STARTUP_DB_ERROR** | startup | Database unreachable at startup | Supabase is down |
| **STARTUP_FAILURE** | startup | Critical error during startup | Missing environment variables |

### Error Logging Flow

```
System Error Occurs
    ↓
Database Service detects error
    ↓
log_system_error() is called
    ↓
Error logged to system_logs table
    ↓
Frontend displays error in dashboard
    ↓
Admin can view error details and metadata
```

### Guaranteed Error Logging

The error logging system is designed to **never crash** the application:
- Error logging is wrapped in try-except blocks
- If database logging fails, error is only logged to console
- System continues running even if logging fails

---

## 📊 Database Schema Updates

### Migration File: `002_add_rfid_logging_fields.sql`

**New Columns:**
```sql
ALTER TABLE rfid_scanners 
ADD COLUMN lane_car_count jsonb DEFAULT '{}'::jsonb;

ALTER TABLE rfid_scanners 
ADD COLUMN cycle_id bigint REFERENCES traffic_cycles(id) ON DELETE SET NULL;

ALTER TABLE rfid_scanners 
ADD COLUMN log_timestamp timestamp with time zone DEFAULT now();
```

**Indexes Created:**
- `idx_rfid_scanners_cycle_id` - Fast lookups by cycle
- `idx_rfid_scanners_log_timestamp` - Fast time-based queries

---

## 🔄 Complete Data Flow Diagram

```
┌─────────────────────┐
│  Raspberry Pi       │
│  (RFID Scanners)    │
└──────────┬──────────┘
           │ (MQTT Publish)
           │ lane_counts, cycle_id, junction_id
           ▼
┌─────────────────────┐
│  HiveMQ Broker      │
│  Topic: flextraff/  │
│  car_counts         │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────┐
│  FastAPI Backend         │
│  mqtt_handler.py         │
│  ✓ Receives MQTT data    │
│  ✓ Validates JSON        │
│  ✓ Logs to RFID table    │
│  ✓ Handles errors        │
└──────────┬───────────────┘
           │
      ┌────┴─────┐
      ▼          ▼
  ┌────────┐  ┌──────────────┐
  │Traffic │  │  Database    │
  │Calc    │  │  Service     │
  └────┬───┘  └──────┬───────┘
       │             │
       │    ┌────────┴────────────┐
       │    │                     │
       ▼    ▼                     ▼
  ┌──────────────────────────────────────────┐
  │         Supabase Database                │
  │  ┌──────────────┐  ┌──────────────────┐ │
  │  │rfid_scanners │  │  system_logs     │ │
  │  │              │  │                  │ │
  │  │• lane_car_   │  │• component       │ │
  │  │  count       │  │• log_level       │ │
  │  │• cycle_id    │  │• message         │ │
  │  │• timestamp   │  │• metadata        │ │
  │  │              │  │• timestamp       │ │
  │  └──────────────┘  └──────────────────┘ │
  └────────────────────┬─────────────────────┘
                       │
                       ▼
  ┌──────────────────────────────┐
  │  React Frontend              │
  │  ✓ Displays RFID logs        │
  │  ✓ Shows system status       │
  │  ✓ Alerts on errors          │
  │  ✓ User management panel     │
  └──────────────────────────────┘
```

---

## 👥 Frontend User Experience

### What Users See

**1. Real-Time RFID Scanner Logs**
- Table showing all recorded vehicle counts
- Columns: Timestamp, Junction, Lane Counts (N/S/E/W), Cycle ID
- Filter by date, junction, or time range
- Export functionality for reporting

**2. System Status Dashboard**
- Connection status (MQTT, Backend, Database)
- Last heartbeat time
- System uptime
- Error alerts with visual indicators

**3. System Logs Viewer**
- All system events and errors
- Color-coded severity levels:
  - 🟢 INFO (green)
  - 🟡 WARNING (yellow)
  - 🔴 ERROR (red)
- Search and filter capabilities
- Detailed error metadata

**4. Error Management**
- Real-time alerts for critical errors
- Error history with stack traces
- Auto-refresh to show new logs
- Export logs for debugging

---

## 🔧 Backend API Reference

### Methods Added to DatabaseService

#### `log_rfid_scanner_data()`
```python
await db_service.log_rfid_scanner_data(
    junction_id=1,
    cycle_id=123,
    lane_car_count={
        "north": 5,
        "south": 3,
        "east": 8,
        "west": 4
    }
)
```

#### `log_system_error()`
```python
await db_service.log_system_error(
    error_message="Connection timeout",
    error_type="FASTAPI_TIMEOUT",
    component="mqtt_handler",
    junction_id=1,
    metadata={"attempted_url": "https://..."}
)
```

#### `log_system_event()`
```python
await db_service.log_system_event(
    message="Backend started successfully",
    log_level="INFO",
    component="startup",
    junction_id=None
)
```

---

## 🚀 Deployment Checklist

### Before Going Live

- [ ] Run migration `002_add_rfid_logging_fields.sql` in Supabase
- [ ] Update `.env` with correct MQTT broker details
- [ ] Configure CORS origins for frontend in `main.py`
- [ ] Test MQTT connectivity to Raspberry Pi
- [ ] Test database connection to Supabase
- [ ] Verify frontend can access logs endpoint
- [ ] Set up monitoring/alerting for errors
- [ ] Test error logging by simulating failures

### Post-Deployment

- [ ] Monitor system logs for startup errors
- [ ] Verify RFID scanner data is being logged
- [ ] Test frontend displays data correctly
- [ ] Check that errors are logged properly
- [ ] Set up daily log cleanup if needed

---

## 🔍 Troubleshooting Guide

### Problem: No RFID data appearing in logs

**Solution:**
1. Check MQTT connection status in system_logs
2. Verify Raspberry Pi is publishing to `flextraff/car_counts`
3. Check JSON payload format matches expected schema
4. Look for JSON_DECODE_ERROR in system logs

### Problem: System crashed and no error was logged

**Solution:**
1. Check both application logs and system_logs table
2. Verify database connection was active
3. Check for STARTUP_FAILURE errors
4. Review console output for unhandled exceptions

### Problem: Missing cycle_id in RFID logs

**Solution:**
1. Ensure Raspberry Pi includes `cycle_id` in MQTT payload
2. Frontend can still display logs without cycle_id (it will be NULL)
3. Add validation in mqtt_handler if cycle_id is required

---

## 📈 Monitoring & Analytics

### Key Metrics to Track

1. **Vehicle Count Trends**
   - Query `rfid_scanners` table
   - Group by hour/day to see patterns
   - Useful for traffic planning

2. **System Health**
   - Count ERROR entries in `system_logs` per hour
   - Track MQTT disconnect/reconnect events
   - Monitor database response times

3. **Error Rate**
   - Calculate percentage of failed cycles
   - Track specific error types over time
   - Identify recurring issues

### Example Queries

```sql
-- Vehicle counts by lane in last hour
SELECT 
  lane_car_count->>'north' as north_count,
  lane_car_count->>'south' as south_count,
  COUNT(*) as occurrences
FROM rfid_scanners
WHERE log_timestamp > NOW() - INTERVAL '1 hour'
GROUP BY lane_car_count;

-- System errors in last 24 hours
SELECT 
  component,
  message,
  COUNT(*) as error_count
FROM system_logs
WHERE log_level = 'ERROR'
AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY component, message;

-- System uptime percentage
SELECT 
  (total_logs - error_logs) * 100.0 / total_logs as uptime_percent
FROM (
  SELECT 
    COUNT(*) as total_logs,
    SUM(CASE WHEN log_level = 'ERROR' THEN 1 ELSE 0 END) as error_logs
  FROM system_logs
  WHERE timestamp > NOW() - INTERVAL '7 days'
);
```

---

## 🔐 Security Considerations

1. **MQTT Security**
   - Using public HiveMQ broker for development
   - For production: Use private broker with authentication
   - Consider TLS/SSL for encrypted messages

2. **Database Security**
   - Using Supabase service key (server-side only)
   - Row-level security (RLS) policies can be added
   - Audit logging via system_logs table

3. **Frontend Security**
   - CORS restricted to known domains
   - Consider rate limiting on API endpoints
   - Implement user authentication for log access

---

## 📱 Support & Debugging

### Enable Debug Logging

Set environment variable:
```bash
export LOG_LEVEL=DEBUG
```

### View Real-Time Logs

**Option 1: System Logs Table**
```sql
SELECT * FROM system_logs 
ORDER BY timestamp DESC 
LIMIT 100;
```

**Option 2: Application Console**
- View Docker logs: `docker logs flextraff-backend`
- View local logs: Check application output

### Generate Test Data

```python
# In backend
await db_service.log_rfid_scanner_data(
    junction_id=1,
    cycle_id=999,
    lane_car_count={"north": 10, "south": 20, "east": 15, "west": 25}
)
```

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-18 | Initial system with RFID logging and error handling |

---

## 📞 Support

For issues or questions about this system:

1. Check [system_logs table](https://supabase.com) for errors
2. Review this documentation
3. Enable debug logging for more details
4. Contact backend team with error codes and timestamps

---

**End of Documentation**
