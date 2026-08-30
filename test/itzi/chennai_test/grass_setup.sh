#!/bin/bash
# Setup GRASS location for Itzi Chennai big square test
# Requires GRASS GIS 8.4: sudo pacman -S grass (Arch) or https://grass.osgeo.org/download/
# This script creates a GRASS database, imports DEM, friction, rain, bctype/bcval, and sets region

set -e
GRASSDB=/tmp/grassdata
LOCATION=itzi_chennai
MAPSET=PERMANENT

echo "Creating GRASS DB at $GRASSDB"
mkdir -p $GRASSDB

# Create location from DEM (EPSG:4326)
grass -c input/dem.tif $GRASSDB/$LOCATION -e 2>&1 | head -20

# Import rasters
grass $GRASSDB/$LOCATION/$MAPSET --exec r.in.gdal input=input/dem.tif output=dem 2>&1 | head -20
grass $GRASSDB/$LOCATION/$MAPSET --exec r.in.gdal input=input/friction.tif output=friction 2>&1 | head
grass $GRASSDB/$LOCATION/$MAPSET --exec r.in.gdal input=input/rain_50mm.tif output=rain 2>&1 | head
grass $GRASSDB/$LOCATION/$MAPSET --exec r.in.gdal input=input/bctype.tif output=bctype 2>&1 | head
grass $GRASSDB/$LOCATION/$MAPSET --exec r.in.gdal input=input/bcval.tif output=bcval 2>&1 | head

# For time-varying rain, create STRDS (here constant 50 mm/hr for 1 hr, then 0)
# Example: t.create and t.register would be needed for space-time rainfall

# Set region to DEM
grass $GRASSDB/$LOCATION/$MAPSET --exec g.region raster=dem 2>&1 | head
grass $GRASSDB/$LOCATION/$MAPSET --exec r.info dem 2>&1 | head -30
grass $GRASSDB/$LOCATION/$MAPSET --exec g.list type=raster 2>&1 | head -20

echo "GRASS setup done. Now run: itzi run chennai.ini"
