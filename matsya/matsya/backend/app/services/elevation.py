import pathlib
import io

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
from PIL import Image

# Primary TIF path: workspace root assets — parents[5] from app/services/elevation.py
# matsya/matsya/backend/app/services/elevation.py -> parents[5] = repo root
TIF = pathlib.Path(__file__).resolve().parents[5] / "assets/CartoDEM_30m_Chennai_EGM96_MSL.tif"
if not TIF.exists():
    for cand in [
        pathlib.Path("assets/CartoDEM_30m_Chennai_EGM96_MSL.tif"),
        pathlib.Path("/app/assets/CartoDEM_30m_Chennai_EGM96_MSL.tif"),
        pathlib.Path(__file__).resolve().parents[2] / "assets/CartoDEM_30m_Chennai_EGM96_MSL.tif",
        pathlib.Path(__file__).resolve().parents[3] / "assets/CartoDEM_30m_Chennai_EGM96_MSL.tif",
        pathlib.Path(__file__).resolve().parents[4] / "assets/CartoDEM_30m_Chennai_EGM96_MSL.tif",
    ]:
        if cand.exists():
            TIF = cand
            break


def hypsometric_color(elev, vmin, vmax):
    """Interpolate hypsometric ramp.
    Ramp: 0.0 #0a3d2e sea, 0.2 #2c5f2d, 0.5 #a8d5a2, 0.7 #d2b48c, 0.85 #8B4513, 1.0 #fefefe
    """
    if vmax == vmin:
        norm = 0.5
    else:
        norm = max(0, min(1, (elev - vmin) / (vmax - vmin)))
    colors = [(10, 61, 46), (44, 95, 45), (168, 213, 162), (210, 180, 140), (139, 69, 19), (254, 254, 254)]
    stops = [0, 0.2, 0.5, 0.7, 0.85, 1.0]
    for i in range(len(stops) - 1):
        if stops[i] <= norm <= stops[i + 1]:
            span = stops[i + 1] - stops[i]
            t = (norm - stops[i]) / span if span != 0 else 0
            r = int(colors[i][0] * (1 - t) + colors[i + 1][0] * t)
            g = int(colors[i][1] * (1 - t) + colors[i + 1][1] * t)
            b = int(colors[i][2] * (1 - t) + colors[i + 1][2] * t)
            return (r, g, b)
    return colors[-1]


def clip_and_render(bbox, width=180, height=180):
    """Clip TIF to bbox and render hypsometric PNG.
    Returns: (array 2D float, png_bytes, stats {min,max,mean,width,height,bbox})
    """
    minLon, minLat, maxLon, maxLat = bbox
    with rasterio.open(TIF) as src:
        window = from_bounds(minLon, minLat, maxLon, maxLat, src.transform)
        arr = src.read(
            1,
            window=window,
            out_shape=(height, width),
            resampling=Resampling.bilinear,
            boundless=True,
            fill_value=np.nan,
        )
        # mask nodata if present (rasterio nodata = -32768)
        if src.nodata is not None:
            # src.nodata may be -32768.0; convert those to nan where they survived bilinear
            # Note: bilinear may interpolate nodata, so approximate check: values very close to nodata
            # For exact equality, mask directly
            arr = np.where(arr == src.nodata, np.nan, arr)
            # also handle near-nodata due to interpolation? keep as is; valid test expects true DEM values
        valid = arr[~np.isnan(arr)]
        if len(valid) == 0:
            vmin, vmax, vmean = 0, 10, 5
        else:
            vmin, vmax, vmean = float(np.min(valid)), float(np.max(valid)), float(np.mean(valid))
        # render PNG via hypsometric per pixel
        rgb = np.zeros((height, width, 3), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                if np.isnan(arr[y, x]):
                    rgb[y, x] = [0, 0, 0]
                else:
                    r, g, b = hypsometric_color(float(arr[y, x]), vmin, vmax)
                    rgb[y, x] = [r, g, b]
        img = Image.fromarray(rgb, "RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png = buf.getvalue()
        stats = {"min": vmin, "max": vmax, "mean": vmean, "width": width, "height": height, "bbox": bbox}
        return arr, png, stats
