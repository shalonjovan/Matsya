from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="MATSYA")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
@app.get("/api/health")
def health(): return {"status":"ok","version":"0.1.0","engine":"anuga-mock"}
