import asyncio
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

# Load environment variables
load_dotenv()


class DatabaseService:
    """
    Supabase Database Service for FlexTraff ATCS Backend
    Handles all database operations including system logging
    """

    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not self.supabase_url or not self.supabase_service_key:
            raise ValueError(
                "Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in environment"
            )

        self.supabase: Client = create_client(
            self.supabase_url, self.supabase_service_key
        )

        self.logger = logging.getLogger("DatabaseService")
        self.logger.setLevel(logging.INFO)

        self.logger.info("✅ DatabaseService initialized")

    # ------------------------------------------------------------------
    # 🔥 SYSTEM LOGGING (SAFE + ASYNC FIXED)
    # ------------------------------------------------------------------

    async def log_system_event(
        self,
        message: str,
        log_level: str = "INFO",
        component: str = "backend",
        junction_id: Optional[int] = None,
    ) -> None:
        """
        Insert system log into system_logs table
        NEVER raises exception (logging must be safe)
        """
        try:
            log_data = {
                "log_level": log_level,
                "component": component,
                "message": message,
                "junction_id": junction_id,
            }

            await asyncio.to_thread(
                lambda: self.supabase.table("system_logs")
                .insert(log_data)
                .execute()
            )

        except Exception as e:
            # Logging should never crash the system
            self.logger.error(f"❌ Failed to insert system log: {e}")

    # ------------------------------------------------------------------
    # 🚗 VEHICLE DETECTIONS
    # ------------------------------------------------------------------

    async def log_vehicle_detection(
        self,
        junction_id: int,
        lane_number: int,
        fastag_id: str,
        vehicle_type: str = "car",
    ) -> Dict[str, Any]:
        try:
            detection_data = {
                "junction_id": junction_id,
                "lane_number": lane_number,
                "fastag_id": fastag_id,
                "vehicle_type": vehicle_type,
                "processing_status": "processed",
            }

            result = await asyncio.to_thread(
                lambda: self.supabase.table("vehicle_detections")
                .insert(detection_data)
                .execute()
            )

            if not result.data:
                raise Exception("No data returned from insert")

            await self.log_system_event(
                message=f"Vehicle detected | FASTag={fastag_id} | lane={lane_number}",
                component="vehicle_detection",
                junction_id=junction_id,
            )

            return result.data[0]

        except Exception as e:
            await self.log_system_event(
                message=str(e),
                log_level="ERROR",
                component="vehicle_detection",
                junction_id=junction_id,
            )
            raise

    # ------------------------------------------------------------------
    # 🚦 TRAFFIC CYCLES
    # ------------------------------------------------------------------

    async def log_traffic_cycle(
        self,
        junction_id: int,
        lane_counts: List[int],
        green_times: List[int],
        cycle_time: int,
        calculation_time_ms: int,
    ) -> Dict[str, Any]:
        try:
            cycle_data = {
                "junction_id": junction_id,
                "total_cycle_time": cycle_time,
                "lane_1_green_time": green_times[0],
                "lane_2_green_time": green_times[1],
                "lane_3_green_time": green_times[2],
                "lane_4_green_time": green_times[3],
                "lane_1_vehicle_count": lane_counts[0],
                "lane_2_vehicle_count": lane_counts[1],
                "lane_3_vehicle_count": lane_counts[2],
                "lane_4_vehicle_count": lane_counts[3],
                "total_vehicles_detected": sum(lane_counts),
                "algorithm_version": "v1.0",
                "calculation_time_ms": calculation_time_ms,
            }

            result = await asyncio.to_thread(
                lambda: self.supabase.table("traffic_cycles")
                .insert(cycle_data)
                .execute()
            )

            if not result.data:
                raise Exception("No data returned from insert")

            await self.log_system_event(
                message=(
                    f"Traffic cycle calculated | "
                    f"cycle={cycle_time}s | vehicles={sum(lane_counts)}"
                ),
                component="traffic_calculator",
                junction_id=junction_id,
            )

            return result.data[0]

        except Exception as e:
            await self.log_system_event(
                message=str(e),
                log_level="ERROR",
                component="traffic_calculator",
                junction_id=junction_id,
            )
            raise

    # ------------------------------------------------------------------
    # 📊 QUERIES
    # ------------------------------------------------------------------

    async def get_current_lane_counts(
        self, junction_id: int, time_window_minutes: int = 5
    ) -> List[Dict[str, Any]]:
        try:
            time_threshold = (
                datetime.utcnow() - timedelta(minutes=time_window_minutes)
            ).isoformat()

            result = await asyncio.to_thread(
                lambda: self.supabase.table("vehicle_detections")
                .select("lane_number")
                .eq("junction_id", junction_id)
                .gte("detection_timestamp", time_threshold)
                .execute()
            )

            lane_counts = {1: 0, 2: 0, 3: 0, 4: 0}
            lane_names = {1: "North", 2: "South", 3: "East", 4: "West"}

            for row in result.data:
                ln = row["lane_number"]
                if ln in lane_counts:
                    lane_counts[ln] += 1

            return [
                {
                    "lane": lane_names[i],
                    "lane_number": i,
                    "count": lane_counts[i],
                }
                for i in range(1, 5)
            ]

        except Exception as e:
            await self.log_system_event(
                message=str(e),
                log_level="ERROR",
                component="lane_count_query",
                junction_id=junction_id,
            )
            return []

    async def get_vehicles_count_by_date(
        self, junction_id: int, target_date: date
    ) -> int:
        try:
            start = target_date.isoformat()
            end = (target_date + timedelta(days=1)).isoformat()

            result = await asyncio.to_thread(
                lambda: self.supabase.table("vehicle_detections")
                .select("id", count="exact")
                .eq("junction_id", junction_id)
                .gte("detection_timestamp", start)
                .lt("detection_timestamp", end)
                .execute()
            )

            return result.count or 0

        except Exception as e:
            await self.log_system_event(
                message=str(e),
                log_level="ERROR",
                component="vehicle_count_query",
                junction_id=junction_id,
            )
            return 0

    async def get_current_traffic_cycle(
        self, junction_id: int
    ) -> Optional[Dict[str, Any]]:
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("traffic_cycles")
                .select("*")
                .eq("junction_id", junction_id)
                .order("cycle_start_time", desc=True)
                .limit(1)
                .execute()
            )

            return result.data[0] if result.data else None

        except Exception as e:
            await self.log_system_event(
                message=str(e),
                log_level="ERROR",
                component="traffic_cycle_query",
                junction_id=junction_id,
            )
            return None

    async def get_all_junctions(self) -> List[Dict[str, Any]]:
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("traffic_junctions")
                .select("*")
                .eq("status", "active")
                .order("junction_name")
                .execute()
            )

            return result.data or []

        except Exception as e:
            await self.log_system_event(
                message=str(e),
                log_level="ERROR",
                component="junction_query",
            )
            return []

    # ------------------------------------------------------------------
    # ❤️ HEALTH
    # ------------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        try:
            await asyncio.to_thread(
                lambda: self.supabase.table("traffic_junctions")
                .select("id")
                .limit(1)
                .execute()
            )

            return {
                "database_connected": True,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "database_connected": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

# ...existing code...

async def log_vehicle_counts(
    self,
    junction_id: int,
    lane_counts: list[int],
    cycle_id: Optional[int] = None
) -> dict:
    """
    Log vehicle counts to system_logs table
    
    Args:
        junction_id: ID of the junction
        lane_counts: List of counts for each lane [lane1, lane2, lane3, lane4]
        cycle_id: Optional traffic cycle ID
    """
    try:
        log_entry = {
            "event_type": "vehicle_count",
            "junction_id": junction_id,
            "description": f"Lane counts detected - Lane1: {lane_counts[0]}, Lane2: {lane_counts[1]}, Lane3: {lane_counts[2]}, Lane4: {lane_counts[3]}, Total: {sum(lane_counts)}",
            "metadata": {
                "lane_1": lane_counts[0],
                "lane_2": lane_counts[1],
                "lane_3": lane_counts[2],
                "lane_4": lane_counts[3],
                "total_vehicles": sum(lane_counts),
                "cycle_id": cycle_id
            }
        }
        
        result = await self.supabase.table("system_logs").insert(log_entry).execute()
        self.logger.info(f"✅ Logged vehicle counts - Junction: {junction_id}, Counts: {lane_counts}")
        return {"status": "success", "data": result.data}
        
    except Exception as e:
        self.logger.error(f"❌ Error logging vehicle counts: {str(e)}")
        return {"error": str(e)}

async def get_vehicle_count_logs(
    self,
    junction_id: int,
    limit: int = 100
) -> dict:
    """
    Retrieve vehicle count logs from system_logs
    
    Args:
        junction_id: ID of the junction
        limit: Number of recent logs to fetch
    """
    try:
        result = (
            await self.supabase.table("system_logs")
            .select("*")
            .eq("junction_id", junction_id)
            .eq("event_type", "vehicle_count")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        
        self.logger.info(f"✅ Retrieved {len(result.data)} vehicle count logs")
        return {"status": "success", "data": result.data}
        
    except Exception as e:
        self.logger.error(f"❌ Error retrieving vehicle count logs: {str(e)}")
        return {"error": str(e)}

async def get_vehicle_counts_by_date(
    self,
    junction_id: int,
    start_date: str,
    end_date: str
) -> dict:
    """
    Get vehicle count logs within a date range
    
    Args:
        junction_id: ID of the junction
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
    """
    try:
        result = (
            await self.supabase.table("system_logs")
            .select("*")
            .eq("junction_id", junction_id)
            .eq("event_type", "vehicle_count")
            .gte("created_at", start_date)
            .lte("created_at", end_date)
            .order("created_at", desc=True)
            .execute()
        )
        
        self.logger.info(f"✅ Retrieved {len(result.data)} logs for date range")
        return {"status": "success", "data": result.data}
        
    except Exception as e:
        self.logger.error(f"❌ Error retrieving date range logs: {str(e)}")
        return {"error": str(e)}