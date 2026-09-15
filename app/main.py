import time
import os
import uuid
import asyncio
from typing import Dict, List, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import init_db, get_db_connection
from app.tariff import calculate_fee
from duitnow_engine import DuitNowDynamicQR, SAMPLE_STATIC_DUITNOW

# Initialize app and templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Initialize QR Engine with the real DuitNow string provided by user
REAL_DUITNOW_QR = "00020201021126560014A000000615000101068900610224602e133f1129ae9ef5dfd3cb5204000053034585802MY5925PERFECT SECURITY & AUT...6002MY8240151624d4b83552c970df6f920824aaf4e04c86e96304762F"
qr_engine = DuitNowDynamicQR(REAL_DUITNOW_QR)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except RuntimeError:
                pass

manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown

app = FastAPI(title="Smart Parking Management API", lifespan=lifespan)

def gate_response(open_gate=False, error_num=0, error_str="noerror"):
    response = {
        "error_num": error_num,
        "error_str": error_str
    }
    if open_gate:
        response["gpio_data"] = [{"ionum": "io1", "action": "on"}]
    return JSONResponse(content=response)

@app.post("/api/lpr/event")
async def handle_lpr_event(
    request: Request,
    type: str = Form(...),
    vdc_type: str = Form(None),
    plate_num: str = Form(None),
    start_time: str = Form(None),
    cam_ip: str = Form(None),
    cam_id: str = Form(None),
    park_id: str = Form(None)
):
    try:
        event_time = int(start_time) if start_time else int(time.time())
    except ValueError:
        event_time = int(time.time())

    db = await get_db_connection()
    try:
        if type == "heartbeat":
            # Poll for any pending gate release requests for this camera
            cursor = await db.execute(
                "SELECT id FROM parking_records WHERE status = 'PAID' AND gate_released = 0 LIMIT 1"
            )
            row = await cursor.fetchone()
            if row:
                record_id = row["id"]
                # Mark as gate released and completed
                await db.execute(
                    "UPDATE parking_records SET gate_released = 1, status = 'COMPLETED' WHERE id = ?",
                    (record_id,)
                )
                await db.commit()
                print(f"[{cam_ip}] Heartbeat: Returning GATE OPEN command for record {record_id}")
                return gate_response(open_gate=True)
                
            return gate_response(open_gate=False)
            
        if type == "online":
            if not vdc_type or not plate_num:
                return gate_response(open_gate=False, error_num=1, error_str="Missing parameters")
                
            if vdc_type == "in":
                # Handle Entry
                cursor = await db.execute(
                    "SELECT id FROM parking_records WHERE plate_num = ? AND status IN ('PARKED', 'PENDING_PAYMENT')",
                    (plate_num,)
                )
                if not await cursor.fetchone():
                    await db.execute(
                        "INSERT INTO parking_records (plate_num, entry_time, status, cam_ip_in) VALUES (?, ?, 'PARKED', ?)",
                        (plate_num, event_time, cam_ip)
                    )
                    await db.commit()
                return gate_response(open_gate=True)

            elif vdc_type == "out":
                # Handle Exit
                cursor = await db.execute(
                    "SELECT id, entry_time FROM parking_records WHERE plate_num = ? AND status = 'PARKED' ORDER BY id DESC LIMIT 1",
                    (plate_num,)
                )
                row = await cursor.fetchone()
                
                if row:
                    record_id = row["id"]
                    entry_time = row["entry_time"]
                    
                    duration_minutes = max(0, (event_time - entry_time) / 60.0)
                    fee = calculate_fee(duration_minutes)
                    
                    if fee <= 0:
                        # Free, open gate immediately
                        await db.execute(
                            "UPDATE parking_records SET exit_time = ?, fee = ?, status = 'COMPLETED', gate_released = 1, cam_ip_out = ? WHERE id = ?",
                            (event_time, 0.0, cam_ip, record_id)
                        )
                        await db.commit()
                        return gate_response(open_gate=True)
                    else:
                        # Requires payment
                        order_id = str(uuid.uuid4())
                        await db.execute(
                            "UPDATE parking_records SET exit_time = ?, fee = ?, status = 'PENDING_PAYMENT', cam_ip_out = ? WHERE id = ?",
                            (event_time, fee, cam_ip, record_id)
                        )
                        await db.execute(
                            "INSERT INTO transactions (order_id, record_id, plate_num, amount, status, created_at) VALUES (?, ?, ?, ?, 'PENDING', ?)",
                            (order_id, record_id, plate_num, fee, int(time.time()))
                        )
                        await db.commit()
                        
                        # Generate dynamic QR
                        qr_image_data = qr_engine.generate_qr_base64(fee)
                        
                        # Broadcast to tablet
                        await manager.broadcast({
                            "event": "SHOW_PAYMENT",
                            "data": {
                                "plate_num": plate_num,
                                "duration_minutes": int(duration_minutes),
                                "amount": fee,
                                "order_id": order_id,
                                "qr_image_data": qr_image_data
                            }
                        })
                        
                        # Return neutral response (do not open gate)
                        return gate_response(open_gate=False)
                else:
                    return gate_response(open_gate=False, error_num=3, error_str="No matching entry found")
                    
    finally:
        await db.close()

    return gate_response(open_gate=False, error_num=4, error_str="Unknown type")

@app.websocket("/ws/exit-kiosk")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/payment/mock-pay/{order_id}")
async def mock_payment_trigger(order_id: str):
    """ Test endpoint to simulate a successful payment from a payment gateway """
    db = await get_db_connection()
    try:
        cursor = await db.execute("SELECT record_id, plate_num FROM transactions WHERE order_id = ? AND status = 'PENDING'", (order_id,))
        row = await cursor.fetchone()
        if row:
            record_id = row["record_id"]
            
            # Update Transaction and Parking Record
            await db.execute("UPDATE transactions SET status = 'PAID' WHERE order_id = ?", (order_id,))
            await db.execute("UPDATE parking_records SET status = 'PAID' WHERE id = ?", (record_id,))
            await db.commit()
            
            # Inform Tablet
            await manager.broadcast({
                "event": "PAYMENT_SUCCESS",
                "data": {
                    "plate_num": row["plate_num"],
                    "order_id": order_id
                }
            })
            
            return {"status": "success", "message": "Payment simulated and gate release queued."}
        return JSONResponse(status_code=404, content={"status": "error", "message": "Pending transaction not found."})
    finally:
        await db.close()

@app.post("/api/payment/pay-latest")
async def pay_latest_transaction():
    """ 
    Endpoint for MacroDroid/Tasker automation. 
    Triggers payment success for the most recently created PENDING transaction.
    """
    db = await get_db_connection()
    try:
        # Find the latest pending transaction
        cursor = await db.execute("SELECT order_id FROM transactions WHERE status = 'PENDING' ORDER BY created_at DESC LIMIT 1")
        row = await cursor.fetchone()
        if row:
            # Trigger the same logic as mock_payment_trigger
            return await mock_payment_trigger(row["order_id"])
        return JSONResponse(status_code=404, content={"status": "error", "message": "No pending transactions found."})
    finally:
        await db.close()

@app.post("/api/payment/webhook")
async def payment_webhook(request: Request):
    """ Real Webhook endpoint for hitpay/curlec etc. """
    payload = await request.json()
    order_id = payload.get("order_id")
    status = payload.get("status")
    
    if status == "PAID":
        return await mock_payment_trigger(order_id)
    return {"status": "ignored"}

@app.get("/kiosk", response_class=HTMLResponse)
async def kiosk_ui(request: Request):
    """ Renders the Kiosk Tablet UI """
    return templates.TemplateResponse(request=request, name="exit_kiosk.html")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """ Renders the Web Dashboard with statistics """
    db = await get_db_connection()
    try:
        # Get currently parked vehicles
        cursor = await db.execute("SELECT plate_num, entry_time FROM parking_records WHERE status IN ('PARKED', 'PENDING_PAYMENT') ORDER BY entry_time DESC")
        parked_vehicles = await cursor.fetchall()
        
        # Get recent exits
        cursor = await db.execute("SELECT plate_num, entry_time, exit_time, fee FROM parking_records WHERE status IN ('COMPLETED', 'PAID') ORDER BY exit_time DESC LIMIT 10")
        recent_exits = await cursor.fetchall()

        # Aggregation Logic (Daily, Weekly, Monthly, Accumulative)
        now = int(time.time())
        
        cursor = await db.execute("SELECT COUNT(*) as c, SUM(fee) as f FROM parking_records WHERE status IN ('COMPLETED', 'PAID') AND exit_time >= strftime('%s', 'now', 'start of day', 'localtime')")
        daily = await cursor.fetchone()
        
        cursor = await db.execute("SELECT COUNT(*) as c, SUM(fee) as f FROM parking_records WHERE status IN ('COMPLETED', 'PAID') AND exit_time >= strftime('%s', 'now', 'weekday 0', '-6 days', 'localtime')")
        weekly = await cursor.fetchone()
        
        cursor = await db.execute("SELECT COUNT(*) as c, SUM(fee) as f FROM parking_records WHERE status IN ('COMPLETED', 'PAID') AND exit_time >= strftime('%s', 'now', 'start of month', 'localtime')")
        monthly = await cursor.fetchone()
        
        cursor = await db.execute("SELECT COUNT(*) as c, SUM(fee) as f FROM parking_records WHERE status IN ('COMPLETED', 'PAID')")
        accum = await cursor.fetchone()

        stats = {
            "daily": {"count": daily["c"] or 0, "fee": daily["f"] or 0.0},
            "weekly": {"count": weekly["c"] or 0, "fee": weekly["f"] or 0.0},
            "monthly": {"count": monthly["c"] or 0, "fee": monthly["f"] or 0.0},
            "accumulative": {"count": accum["c"] or 0, "fee": accum["f"] or 0.0},
        }
        
    finally:
        await db.close()
        
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={
            "parked_vehicles": parked_vehicles,
            "recent_exits": recent_exits,
            "current_time": now,
            "stats": stats
        }
    )
