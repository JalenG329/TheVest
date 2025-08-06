import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np

from degirum_tools.tile_compound_models import TileExtractorPseudoModel, TileModel, LocalGlobalTileModel, BoxFusionLocalGlobalTileModel
from degirum_tools import NmsBoxSelectionPolicy, NmsOptions

model = dg.load_model(
    model_name="depth_anything_v2--224x224_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

