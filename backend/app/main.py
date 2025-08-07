from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api import devices, groups, geofences, integrations 
import os

app = FastAPI()

app.include_router(devices.router, prefix="/api/v1/devices", tags=["devices"])
app.include_router(groups.router, prefix="/api/v1/groups", tags=["groups"])
app.include_router(geofences.router, prefix="/api/v1/geofences", tags=["geofences"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join("app", "static", "index.html"))

@app.get("/favicon.ico")
async def get_favicon():
    favicon_path = os.path.join("app", "static", "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404, detail="Favicon not found")

@app.get("/app.js")
async def serve_app_js():
    return FileResponse(os.path.join("app", "static", "app.js"))

@app.get("/geofences.js")
async def serve_geofences_js():
    return FileResponse(os.path.join("app", "static", "geofences.js"))

@app.get("/style.css")
async def serve_style_css():
    return FileResponse(os.path.join("app", "static", "style.css"))
