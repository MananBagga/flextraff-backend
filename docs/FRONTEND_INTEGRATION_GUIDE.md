# Frontend Integration Guide: RFID Logging & System Monitoring

## 📱 What You Need to Display on Frontend

Your React dashboard should display data from two main sources:

### 1. RFID Scanner Logs Table

**What:** Real-time vehicle count records from RFID scanners

**Database Table:** `rfid_scanners`

**Columns to Display:**

| Column | Type | Description |
|--------|------|-------------|
| log_timestamp | timestamp | When the scan occurred |
| junction_id | integer | Which junction (1, 2, 3, etc.) |
| lane_car_count | JSON | {north: 5, south: 3, east: 8, west: 4} |
| cycle_id | integer | Link to traffic cycle |

**Example Row:**
```
Timestamp: 2026-01-18 14:32:45 UTC
Junction: Junction 1 (Main Street)
North Lane: 5 cars
South Lane: 3 cars
East Lane: 8 cars
West Lane: 4 cars
Cycle ID: 123
```

**Supabase Query:**
```javascript
const { data, error } = await supabase
  .from('rfid_scanners')
  .select('*')
  .order('log_timestamp', { ascending: false })
  .limit(100);
```

### 2. System Logs Table

**What:** System events and errors for monitoring backend health

**Database Table:** `system_logs`

**Columns to Display:**

| Column | Type | Description |
|--------|------|-------------|
| timestamp | timestamp | When event occurred |
| component | text | Which part (startup, mqtt_handler, rfid_scanner, etc.) |
| log_level | text | INFO, ERROR, WARNING |
| message | text | What happened |
| junction_id | integer | Which junction (if applicable) |
| metadata | JSON | Additional details |

**Example Rows:**

✅ INFO Log:
```
Timestamp: 2026-01-18 14:30:00 UTC
Component: startup
Level: INFO (green)
Message: FlexTraff backend started successfully
```

❌ ERROR Log:
```
Timestamp: 2026-01-18 14:32:15 UTC
Component: mqtt_handler
Level: ERROR (red)
Message: FASTAPI_TIMEOUT: FastAPI request timed out after 30 seconds
Junction: 1
Metadata: {"attempted_url": "https://flextraff-backend.onrender.com/calculate-timing"}
```

**Supabase Query:**
```javascript
const { data, error } = await supabase
  .from('system_logs')
  .select('*')
  .order('timestamp', { ascending: false })
  .limit(100);

// Filter by error level
const { data: errors } = await supabase
  .from('system_logs')
  .select('*')
  .eq('log_level', 'ERROR')
  .order('timestamp', { ascending: false });
```

---

## 🎨 Suggested Dashboard Components

### 1. RFID Scanner Logs Component

```jsx
import { useEffect, useState } from 'react';
import { supabase } from './supabaseClient';

export function RFIDLogsPanel() {
  const [logs, setLogs] = useState([]);
  const [junction, setJunction] = useState(null);

  useEffect(() => {
    fetchLogs();
    // Auto-refresh every 5 seconds
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, [junction]);

  const fetchLogs = async () => {
    let query = supabase
      .from('rfid_scanners')
      .select('*')
      .order('log_timestamp', { ascending: false })
      .limit(50);
    
    if (junction) {
      query = query.eq('junction_id', junction);
    }

    const { data } = await query;
    setLogs(data || []);
  };

  return (
    <div className="rfid-logs-panel">
      <h2>🚗 RFID Scanner Logs</h2>
      
      <select onChange={(e) => setJunction(e.target.value)}>
        <option value="">All Junctions</option>
        <option value="1">Junction 1</option>
        <option value="2">Junction 2</option>
      </select>

      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Junction</th>
            <th>North</th>
            <th>South</th>
            <th>East</th>
            <th>West</th>
            <th>Cycle ID</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id}>
              <td>{new Date(log.log_timestamp).toLocaleString()}</td>
              <td>Junction {log.junction_id}</td>
              <td>{log.lane_car_count.north}</td>
              <td>{log.lane_car_count.south}</td>
              <td>{log.lane_car_count.east}</td>
              <td>{log.lane_car_count.west}</td>
              <td>{log.cycle_id}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### 2. System Status Component

```jsx
export function SystemStatusPanel() {
  const [status, setStatus] = useState({
    mqtt: 'connected',
    database: 'connected',
    lastError: null
  });

  useEffect(() => {
    checkSystemHealth();
    const interval = setInterval(checkSystemHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  const checkSystemHealth = async () => {
    const { data: recentLogs } = await supabase
      .from('system_logs')
      .select('*')
      .order('timestamp', { ascending: false })
      .limit(1);

    if (recentLogs && recentLogs[0]) {
      const lastLog = recentLogs[0];
      setStatus({
        ...status,
        lastError: lastLog.log_level === 'ERROR' ? lastLog : null
      });
    }
  };

  return (
    <div className="system-status">
      <h2>🔧 System Status</h2>
      
      <div className={`status-indicator ${status.mqtt}`}>
        📡 MQTT Broker: Connected
      </div>
      
      <div className={`status-indicator ${status.database}`}>
        🗄️ Database: Connected
      </div>

      {status.lastError && (
        <div className="error-alert">
          ⚠️ {status.lastError.message}
          <small>{new Date(status.lastError.timestamp).toLocaleString()}</small>
        </div>
      )}
    </div>
  );
}
```

### 3. System Logs Component

```jsx
export function SystemLogsPanel() {
  const [logs, setLogs] = useState([]);
  const [filterLevel, setFilterLevel] = useState(null);

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, [filterLevel]);

  const fetchLogs = async () => {
    let query = supabase
      .from('system_logs')
      .select('*')
      .order('timestamp', { ascending: false })
      .limit(100);
    
    if (filterLevel) {
      query = query.eq('log_level', filterLevel);
    }

    const { data } = await query;
    setLogs(data || []);
  };

  const getLevelColor = (level) => {
    return {
      'INFO': '#4CAF50',
      'WARNING': '#FFC107',
      'ERROR': '#F44336'
    }[level] || '#999';
  };

  return (
    <div className="system-logs-panel">
      <h2>📋 System Logs</h2>

      <div className="filters">
        <button 
          className={filterLevel === null ? 'active' : ''}
          onClick={() => setFilterLevel(null)}
        >
          All
        </button>
        <button 
          className={filterLevel === 'INFO' ? 'active' : ''}
          onClick={() => setFilterLevel('INFO')}
        >
          ✅ Info
        </button>
        <button 
          className={filterLevel === 'ERROR' ? 'active' : ''}
          onClick={() => setFilterLevel('ERROR')}
        >
          ❌ Errors
        </button>
      </div>

      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Level</th>
            <th>Component</th>
            <th>Message</th>
            <th>Junction</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id}>
              <td>{new Date(log.timestamp).toLocaleString()}</td>
              <td>
                <span 
                  style={{
                    backgroundColor: getLevelColor(log.log_level),
                    color: 'white',
                    padding: '2px 8px',
                    borderRadius: '4px'
                  }}
                >
                  {log.log_level}
                </span>
              </td>
              <td>{log.component}</td>
              <td title={log.message}>{log.message}</td>
              <td>{log.junction_id || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

## 🎯 User Dashboard Layout

```
┌─────────────────────────────────────────────┐
│         🚦 FlexTraff Traffic Dashboard      │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │  🔧 System Status                    │  │
│  │  📡 MQTT: Connected                  │  │
│  │  🗄️  Database: Connected             │  │
│  │  ⚠️  Last Error: 2 min ago           │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │  🚗 RFID Scanner Logs                │  │
│  │  [Filter by Junction: ▼]             │  │
│  │                                      │  │
│  │  Timestamp | Junction | N|S|E|W | ID│  │
│  │  14:32:45  | Junc 1   | 5|3|8|4 |123│  │
│  │  14:32:15  | Junc 1   | 4|2|7|3 |122│  │
│  │  14:31:45  | Junc 1   | 6|4|9|5 |121│  │
│  │                                      │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │  📋 System Logs                      │  │
│  │  [All] [Info] [Errors]               │  │
│  │                                      │  │
│  │  Time   | Level | Component | Msg   │  │
│  │  14:30  | ❌ ERR| mqtt_hand | Time- │  │
│  │  14:15  | ✅ INF| startup   | Start │  │
│  │  14:10  | ✅ INF| rfid_scan | Data- │  │
│  │                                      │  │
│  └──────────────────────────────────────┘  │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 🔄 Real-Time Updates (Optional)

For live updates without page refresh, use Supabase Realtime:

```javascript
const subscription = supabase
  .from('rfid_scanners')
  .on('*', payload => {
    console.log('New RFID log:', payload.new);
    setLogs(prev => [payload.new, ...prev]);
  })
  .subscribe();

return () => {
  subscription.unsubscribe();
};
```

---

## 📊 Export Functionality

Allow users to export logs for reporting:

```javascript
const exportLogs = (logs, filename) => {
  const csv = [
    ['Timestamp', 'Component', 'Level', 'Message', 'Junction'],
    ...logs.map(log => [
      log.timestamp,
      log.component,
      log.log_level,
      log.message,
      log.junction_id
    ])
  ]
  .map(row => row.join(','))
  .join('\n');

  const blob = new Blob([csv], { type: 'text/csv' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
};
```

---

## 🔐 Permission Requirements

The frontend user should have Supabase read access to:
- `rfid_scanners` (full select)
- `system_logs` (full select)

Optional write access if implementing additional features:
- Can add later for admin notes or manual logging

---

## 🚀 Deployment Notes

1. **Update CORS** in backend `main.py` to allow your frontend domain
2. **Test with real MQTT data** before deploying
3. **Set up error alerts** to notify admins of critical errors
4. **Monitor performance** - logs can grow large, consider archiving old data
5. **User training** - teach admins how to read and filter logs

---

**Questions?** See the main documentation: `SYSTEM_FLOW_AND_LOGGING.md`
