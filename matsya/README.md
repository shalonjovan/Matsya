
# MATSYA — matsya/matsya

Run:
```
# backend
cd matsya/matsya/backend && pip install -r requirements.txt && uvicorn app.main:app --reload
# frontend
cd matsya/matsya/frontend && npm install && npm run dev
# docker
docker-compose up --build
```
Seed demo: Chennai big square 180×180 @30m seeded from test/TELEMAC-2D/test-2.0/input/dem_clipped.tif
