
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
import io, csv, json
from app.services.simulation_store import store
from app.services import analysis

router = APIRouter(prefix="/api/simulations/{sim_id}/export", tags=["exports"])

@router.get("")
def export_sim(sim_id: str, format: str = "json"):
    sim = store.get(sim_id)
    if not sim: raise HTTPException(404, "simulation not found")
    fmt = format.lower()
    if fmt == "csv":
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["id","name","maxDepth","floodedArea"])
        areas = analysis.affected_areas(sim)
        for a in areas: w.writerow([sim.id, sim.name, a["maxDepth"], a["duration"]])
        return Response(content=out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{sim.name}.csv"'})
    if fmt == "geojson":
        gj = {"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[sim.area.bbox[0], sim.area.bbox[1]]},"properties":{"name":sim.name}}]}
        return Response(content=json.dumps(gj), media_type="application/geo+json", headers={"Content-Disposition": f'attachment; filename="{sim.name}.geojson"'})
    if fmt == "png":
        # 1x1 png stub
        import base64
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=")
        return StreamingResponse(io.BytesIO(png), media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{sim.name}.png"'})
    if fmt == "pdf":
        pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
        return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{sim.name}.pdf"'})
    if fmt == "matsya":
        from app.services.package_service import create_matsya
        data = create_matsya(sim)
        return StreamingResponse(io.BytesIO(data), media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{sim.name}.matsya"'})
    # default json
    return sim.model_dump(mode="json") if hasattr(sim,"model_dump") else sim
