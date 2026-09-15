from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import uvicorn
from duitnow_engine import DuitNowDynamicQR, SAMPLE_STATIC_DUITNOW

app = FastAPI(title="DuitNow QR Demo Server")

engine = DuitNowDynamicQR(SAMPLE_STATIC_DUITNOW)

@app.get("/api/qr/preview", response_class=HTMLResponse)
async def qr_preview(amount: float = Query(..., description="Transaction amount (RM)")):
    try:
        dynamic_payload = engine.generate_dynamic_payload(amount)
        qr_b64 = engine.generate_qr_base64(amount)
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>DuitNow QR Preview</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; background-color: #f4f7f6; margin: 0; }}
                .card {{ background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; max-width: 450px; width: 100%; }}
                h1 {{ color: #e91e63; margin-bottom: 5px; }}
                h2 {{ color: #2c3e50; margin-top: 0; font-size: 2.5em; }}
                img {{ width: 100%; max-width: 300px; height: auto; border: 2px solid #ecf0f1; border-radius: 12px; margin: 20px 0; }}
                .payload-box {{ background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 8px; word-break: break-all; font-family: monospace; font-size: 0.9em; text-align: left; line-height: 1.4; }}
                .tag {{ color: #e74c3c; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>DuitNow Dynamic QR</h1>
                <h2>RM {amount:.2f}</h2>
                <img src="{qr_b64}" alt="DuitNow QR Code">
                <div class="payload-box">
                    <strong>Raw Payload String:</strong><br><br>
                    {dynamic_payload}
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error</h1><p>{str(e)}</p>", status_code=500)

if __name__ == "__main__":
    print("Starting DuitNow QR Demo Server on http://localhost:8001")
    # For testing, you can visit: http://localhost:8001/api/qr/preview?amount=3.50
    uvicorn.run("demo_server:app", host="0.0.0.0", port=8001, reload=True)
