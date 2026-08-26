#!/bin/bash
# Launch live visualization server
echo "MATSYA SWMM Live Visualization"
echo "Serving at http://localhost:8000"
echo "Open http://localhost:8000 in browser"
echo "Press Ctrl+C to stop"
python3 -m http.server 8000 --directory "$(dirname "$0")"
