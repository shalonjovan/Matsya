"""Forecast rain endpoint (optional input layer)."""
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.get("/rain")
def forecast_rain_ep(minLon: float = Query(...), minLat: float = Query(...),
                     maxLon: float = Query(...), maxLat: float = Query(...),
                     hours: int = Query(6, ge=1, le=48)):
    try:
        from app.services.rainfall_forecast import forecast_rain, ForecastUnavailable
    except ImportError as e:
        raise HTTPException(503, "forecast-unavailable: module missing (%s)" % e)
    try:
        return forecast_rain([minLon, minLat, maxLon, maxLat], hours=hours)
    except ForecastUnavailable as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(503, "forecast-unavailable: %s. Use constant mode." % e)
