# Quick Reference: RFID Logging & Error Handling

## 🎯 One-Page Guide for Developers

### What Changed?

**New Database Columns in `rfid_scanners` table:**
- `lane_car_count` (JSONB) - Vehicle counts with named lanes
- `cycle_id` (bigint) - Links to traffic_cycles table
- `log_timestamp` (timestamp) - When data was logged

### MQTT Data Format Expected

```json
{
  "lane_counts": [5, 3, 8, 4],
  "cycle_id": 123,
  "junction_id": 1
}
```

### What Gets Logged?

#### ✅ RFID Scanner Data
- **When:** Every time MQTT message is received
- **Table:** `rfid_scanners`
- **Data:** Vehicle counts + cycle ID + timestamp

#### ✅ System Events
- **When:** Backend starts, MQTT connects, etc.
- **Table:** `system_logs`
- **Level:** INFO

#### ❌ System Errors
- **When:** Connection failures, timeouts, exceptions
- **Table:** `system_logs`
- **Level:** ERROR
- **Includes:** Error type, message, metadata

### Code Examples

#### Log RFID Data
```python
from app.services.database_service import DatabaseService

db = DatabaseService()

# Log vehicle counts from MQTT
await db.log_rfid_scanner_data(
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

#### Log System Error
```python
await db.log_system_error(
    error_message="MQTT connection failed",
    error_type="MQTT_CONNECT_ERROR",
    component="mqtt_handler",
    junction_id=1,
    metadata={"broker": "broker.hivemq.com"}
)
```

#### Log System Event
```python
await db.log_system_event(
    message="Backend started successfully",
    log_level="INFO",
    component="startup"
)
```

### Error Types Reference

| Error Type | Component | When It Happens |
|-----------|-----------|-----------------|
| MQTT_HANDLER_ERROR | mqtt_handler | Unhandled exception |
| RFID_LOGGING_ERROR | rfid_scanner | Database insert fails |
| FASTAPI_TIMEOUT | mqtt_handler | API call > 30 seconds |
| FASTAPI_CONNECT_ERROR | mqtt_handler | Can't reach backend |
| JSON_DECODE_ERROR | mqtt_handler | Invalid JSON received |
| MQTT_SUBSCRIPTION_ERROR | mqtt_startup | Topic subscribe fails |
| STARTUP_DB_ERROR | startup | Database not available |
| STARTUP_FAILURE | startup | Critical startup error |

### Database Queries

**View all RFID logs:**
```sql
SELECT * FROM rfid_scanners ORDER BY log_timestamp DESC;
```

**View RFID logs for specific junction:**
```sql
SELECT * FROM rfid_scanners 
WHERE junction_id = 1 
ORDER BY log_timestamp DESC;
```

**View system errors:**
```sql
SELECT * FROM system_logs 
WHERE log_level = 'ERROR' 
ORDER BY timestamp DESC;
```

**View errors from last hour:**
```sql
SELECT * FROM system_logs 
WHERE timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC;
```

### Migration to Run

```bash
# File: migrations/002_add_rfid_logging_fields.sql
# Run in Supabase SQL Editor
```

Creates:
- `rfid_scanners.lane_car_count` column
- `rfid_scanners.cycle_id` column
- `rfid_scanners.log_timestamp` column
- Performance indexes

### Frontend Integration

**Endpoint to get RFID logs:**
```
GET /api/rfid-logs?junction_id=1&limit=100
```

**Endpoint to get system logs:**
```
GET /api/system-logs?level=ERROR&hours=24
```

### Testing Error Logging

1. **Simulate MQTT error:**
   ```python
   await db.log_system_error(
       error_message="Test error message",
       error_type="TEST_ERROR",
       component="test"
   )
   ```

2. **Check system_logs table** - Should see new entry

3. **Check frontend** - Error should appear in dashboard

### Key Files Modified

- `app/services/database_service.py` - Added logging methods
- `mqtt_handler.py` - Added RFID logging + error handling
- `main.py` - Added startup/shutdown logging
- `migrations/002_add_rfid_logging_fields.sql` - Schema updates

### Important Notes

⚠️ **Error logging is safe:**
- Never crashes the system
- Wrapped in try-except blocks
- Logs to console if database fails

📊 **Data is queryable:**
- Index on `cycle_id` for fast lookups
- Index on `log_timestamp` for time-based queries
- JSONB column allows advanced querying

🔄 **System is traceable:**
- Every action logged
- Every error captured
- Complete audit trail available

---

**Need more details? See:** `SYSTEM_FLOW_AND_LOGGING.md`
