from fastapi_mqtt import FastMQTT, MQTTConfig
import json
import httpx
import asyncio
import logging
# existing imports...
from ws_broadcast import manager  # import the manager to broadcast messages
from app.services.database_service import DatabaseService

logger = logging.getLogger(__name__)
db_service = DatabaseService()

# --- MQTT Configuration ---
mqtt_config = MQTTConfig(
    host="broker.hivemq.com",
    port=1883,
    keepalive=60,
    version=4  # MQTT v3.1.1
)
mqtt = FastMQTT(config=mqtt_config)


@mqtt.on_connect()
def connect(client, flags, rc, properties):
    """Called when MQTT connects to broker"""
    print("=" * 60)
    print("✅ MQTT CONNECTED to broker.hivemq.com")
    print("=" * 60)
    
    # Subscribe to the car counts topic
    mqtt.client.subscribe("flextraff/car_counts", qos=1)
    print("📡 Subscribed to topic: flextraff/car_counts")
    print("🎧 Listening for messages from Raspberry Pi...\n")


@mqtt.on_disconnect()
def disconnect(client, packet, exc=None):
    """Called when MQTT disconnects"""
    print("⚠️ MQTT Disconnected from broker")


@mqtt.on_subscribe()
def subscribe(client, mid, qos, properties):
    """Called when subscription is confirmed"""
    print(f"✅ Subscription confirmed (mid={mid}, qos={qos})")


@mqtt.on_message()
async def message_handler(client, topic, payload, qos, properties):
    """
    Main message handler - receives car counts from Pi
    and sends back calculated green times
    
    Expected MQTT payload format:
    {
        "lane_counts": [north_count, south_count, east_count, west_count],
        "cycle_id": 123,
        "junction_id": 1
    }
    """
    print("\n" + "=" * 60)
    print(f"📩 MQTT MESSAGE RECEIVED on topic: {topic}")
    print("=" * 60)

    try:
        # Decode the payload
        data = json.loads(payload.decode())
        print(f"📥 Car count data from Pi: {data}")
        
        lane_counts = data.get("lane_counts", [])
        junction_id = data.get("junction_id", 1)
        cycle_id = data.get("cycle_id")
        
        print(f"🚗 Lane counts: {lane_counts}")
        print(f"🚦 Junction ID: {junction_id}")
        print(f"🔄 Cycle ID: {cycle_id}")

        # Log RFID scanner data with lane car counts
        if cycle_id:
            try:
                # Convert lane_counts array to named dictionary
                lane_car_count_dict = {
                    "north": lane_counts[0] if len(lane_counts) > 0 else 0,
                    "south": lane_counts[1] if len(lane_counts) > 1 else 0,
                    "east": lane_counts[2] if len(lane_counts) > 2 else 0,
                    "west": lane_counts[3] if len(lane_counts) > 3 else 0,
                }
                
                # Get the latest traffic cycle ID to link with RFID log
                # (Note: You may need to pass the actual traffic_cycles table ID)
                await db_service.log_rfid_scanner_data(
                    junction_id=junction_id,
                    cycle_id=cycle_id,
                    lane_car_count=lane_car_count_dict,
                )
                print("✅ RFID scanner data logged successfully")
            except Exception as e:
                print(f"⚠️  Warning: Failed to log RFID scanner data: {e}")
                await db_service.log_system_error(
                    error_message=f"Failed to log RFID data: {str(e)}",
                    error_type="RFID_LOGGING_FAILED",
                    component="mqtt_handler",
                    junction_id=junction_id,
                )

        # Call FastAPI endpoint to calculate timing
        print("\n📤 Calling FastAPI /calculate-timing endpoint...")
        
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            try:
                response = await http_client.post(
                    "https://flextraff-backend.onrender.com/calculate-timing",
                    json=data
                )
                
                print(f"📊 FastAPI Response Status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Calculated green times: {result.get('green_times')}")
                    print(f"⏱️  Total cycle time: {result.get('cycle_time')}s")
                    
                    # Publish green times back to Pi
                    green_times_payload = json.dumps({
                        "green_times": result.get("green_times"),
                        "cycle_time": result.get("cycle_time"),
                        "junction_id": junction_id,
                        "cycle_id": cycle_id
                    })
                    
                    mqtt.client.publish(
                        "flextraff/green_times", 
                        green_times_payload,
                        qos=1,
                        retain=False
                    )
                    
                    print(f"📡 Published green times to Pi on topic: flextraff/green_times")
                    print(f"✅ MQTT message processing complete\n")
                    
                else:
                    error_msg = f"FastAPI returned error {response.status_code}: {response.text}"
                    print(f"❌ {error_msg}")
                    await db_service.log_system_error(
                        error_message=error_msg,
                        error_type="FASTAPI_ERROR",
                        component="mqtt_handler",
                        junction_id=junction_id,
                    )
                    
            except httpx.TimeoutException as e:
                error_msg = "FastAPI request timed out after 30 seconds"
                print(f"❌ {error_msg}")
                await db_service.log_system_error(
                    error_message=error_msg,
                    error_type="FASTAPI_TIMEOUT",
                    component="mqtt_handler",
                    junction_id=junction_id,
                )
            except httpx.ConnectError as e:
                error_msg = "Could not connect to FastAPI at https://flextraff-backend.onrender.com"
                print(f"❌ {error_msg}")
                await db_service.log_system_error(
                    error_message=error_msg,
                    error_type="FASTAPI_CONNECT_ERROR",
                    component="mqtt_handler",
                    junction_id=junction_id,
                )
            except Exception as e:
                error_msg = f"Error calling FastAPI: {type(e).__name__}: {e}"
                print(f"❌ {error_msg}")
                await db_service.log_system_error(
                    error_message=str(e),
                    error_type="FASTAPI_EXCEPTION",
                    component="mqtt_handler",
                    junction_id=junction_id,
                )

    except json.JSONDecodeError as e:
        error_msg = f"Failed to decode JSON payload: {e}"
        print(f"❌ {error_msg}")
        print(f"   Raw payload: {payload}")
        await db_service.log_system_error(
            error_message=error_msg,
            error_type="JSON_DECODE_ERROR",
            component="mqtt_handler",
        )
    except Exception as e:
        error_msg = f"MQTT message handler error: {type(e).__name__}: {e}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        await db_service.log_system_error(
            error_message=str(e),
            error_type="MQTT_HANDLER_ERROR",
            component="mqtt_handler",
        )


# Export the mqtt instance
__all__ = ['mqtt']