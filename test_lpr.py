import pytest
from fastapi.testclient import TestClient
from app.main import app
import time
import os
import aiosqlite
import asyncio

client = TestClient(app)

def test_heartbeat():
    with TestClient(app) as client:
        response = client.post("/api/lpr/event", data={"type": "heartbeat"})
        assert response.status_code == 200
        assert response.json() == {"error_num": 0, "error_str": "noerror"}

def test_entry_and_exit():
    # Setup test DB
    import os
    db_path = os.path.join(os.path.dirname(__file__), "parking_records.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    
    with TestClient(app) as client:
        # 1. Entry Event
        entry_time = int(time.time()) - 3600 # 1 hour ago
        response = client.post(
            "/api/lpr/event", 
            data={
                "type": "online",
                "vdc_type": "in",
                "plate_num": "BEE1234",
                "start_time": str(entry_time),
                "cam_ip": "192.168.1.100"
            }
        )
        assert response.status_code == 200
        assert response.json()["error_num"] == 0
        assert response.json()["gpio_data"][0]["action"] == "on"

        # 2. Exit Event
        exit_time = int(time.time())
        response = client.post(
            "/api/lpr/event", 
            data={
                "type": "online",
                "vdc_type": "out",
                "plate_num": "BEE1234",
                "start_time": str(exit_time),
                "cam_ip": "192.168.1.101"
            }
        )
        assert response.status_code == 200
        assert response.json()["error_num"] == 0
        assert response.json()["gpio_data"][0]["action"] == "on"
        
        # 3. Missing Entry test
        response = client.post(
            "/api/lpr/event", 
            data={
                "type": "online",
                "vdc_type": "out",
                "plate_num": "XYZ9999",
                "start_time": str(exit_time),
                "cam_ip": "192.168.1.101"
            }
        )
        assert response.status_code == 200
        assert response.json()["error_num"] == 3

if __name__ == "__main__":
    print("Running tests...")
    test_heartbeat()
    print("Heartbeat test passed.")
    test_entry_and_exit()
    print("Entry/Exit test passed.")
    print("All tests passed!")
