from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.simulations import router as simulations_router

app = FastAPI(title="MATSYA")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(simulations_router)
@app.get("/api/health")
def health(): return {"status":"ok","version":"0.1.0","engine":"anuga-mock"}
