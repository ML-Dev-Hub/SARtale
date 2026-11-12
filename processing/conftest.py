import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import os

# Tests never read the Copernicus DEM over the network (sartale.demmask): the window statistics then use every valid
# pixel, as a build without the DEM does. A test that needs the mask writes the DEM into the lake's cache itself.
os.environ.setdefault("SARTALE_DEM_OFFLINE", "1")
