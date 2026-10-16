"""Read a north-up EPSG:3857 GeoTIFF and prepare the Cesium tile config."""

import argparse
import json
import math
from pathlib import Path

from osgeo import gdal, osr


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("geotiff", nargs="?", default="park_3857.tif")
parser.add_argument("--max-zoom", type=int, default=18)
args = parser.parse_args()
if not 0 <= args.max_zoom <= 22:
    parser.error("--max-zoom must be between 0 and 22")

gdal.UseExceptions()
dataset = gdal.Open(args.geotiff)
source_srs = dataset.GetSpatialRef()
mercator = osr.SpatialReference()
mercator.ImportFromEPSG(3857)
mercator.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
if source_srs is None:
    raise SystemExit("Missing CRS. Complete georeferencing before continuing.")
source_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
if not source_srs.IsSame(mercator):
    raise SystemExit("Expected EPSG:3857. Reproject with gdalwarp, not gdal_edit.")

gt = dataset.GetGeoTransform()
if abs(gt[2]) > 1e-10 or abs(gt[4]) > 1e-10 or gt[1] <= 0 or gt[5] >= 0:
    raise SystemExit("Expected a north-up raster. Normalize it with gdalwarp first.")
if dataset.RasterCount not in (3, 4) or any(
    dataset.GetRasterBand(i).DataType != gdal.GDT_Byte
    for i in range(1, dataset.RasterCount + 1)
):
    raise SystemExit("This example expects an RGB or RGBA Byte image.")

xmin, ymax = gt[0], gt[3]
xmax = xmin + dataset.RasterXSize * gt[1]
ymin = ymax + dataset.RasterYSize * gt[5]
world_half = math.pi * 6378137.0
if not (-world_half < xmin < xmax < world_half and -world_half < ymin < ymax < world_half):
    raise SystemExit("Outside the supported local Web Mercator extent.")

wgs84 = osr.SpatialReference()
wgs84.ImportFromEPSG(4326)
wgs84.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
transform = osr.CoordinateTransformation(source_srs, wgs84)
west, south, east, north = transform.TransformBounds(xmin, ymin, xmax, ymax, 21)

config = {
    "bounds": [west, south, east, north],
    "minimumLevel": 0,
    "maximumLevel": args.max_zoom,
    "url": "./tiles/{z}/{x}/{y}.png",
    "credit": "Local park image — replace with the actual image source",
}
Path("config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

lines = [
    f"Source: {args.geotiff}",
    f"Raster size: {dataset.RasterXSize} x {dataset.RasterYSize}",
    f"Projected pixel size: {gt[1]:.6f} x {abs(gt[5]):.6f} Web Mercator units",
    f"WGS84 bounds [west, south, east, north]: {config['bounds']}",
    "z: estimated rectangular tile count",
]
total = 0
for z in range(args.max_zoom + 1):
    span = 2 * world_half / (2**z)
    left = max(0, math.floor((xmin + world_half) / span))
    right = min(2**z - 1, math.ceil((xmax + world_half) / span) - 1)
    top = max(0, math.floor((world_half - ymax) / span))
    bottom = min(2**z - 1, math.ceil((world_half - ymin) / span) - 1)
    count = (right - left + 1) * (bottom - top + 1)
    total += count
    lines.append(f"{z}: {count} (x={left}..{right}, y={top}..{bottom})")
lines.append(f"Total estimate: {total}")
if not any(
    dataset.GetRasterBand(i).GetColorInterpretation() == gdal.GCI_AlphaBand
    for i in range(1, dataset.RasterCount + 1)
):
    lines.append("WARNING: No alpha band. Check transparent edges before tiling.")
if total > 10000:
    lines.append("Large output: lower --max-zoom or reduce the geographic coverage first.")
report = "\n".join(lines) + "\n"
Path("tile-plan.txt").write_text(report, encoding="utf-8")
print(report)
print("Created config.json and tile-plan.txt. Keep GDAL zoom options consistent with config.json.")
