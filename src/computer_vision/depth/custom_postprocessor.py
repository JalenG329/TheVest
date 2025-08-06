"""
Custom depth postprocessor for haptic feedback vest system.
Optimized for real-time depth processing and vibration mapping.
"""

import cv2
import numpy as np
import degirum as dg


def dequantize(result):
    """Dequantize the depth data."""
    zero_pt = result['quantization']['zero']
    scale = result['quantization']['scale']
    
    dq_data = (result['data'].astype(np.float32) - zero_pt) * scale
    return dq_data


def sigmoid(z):
    """Sigmoid activation function."""
    return 1 / (1 + np.exp(-z))


class DepthResults(dg.postprocessor.InferenceResults):
    """
    Custom depth postprocessor optimized for haptic feedback.
    Provides both raw depth data for vibration analysis and 
    visualization-ready depth maps.
    """
    
    # Color map for visualization
    color_map = cv2.COLORMAP_TURBO  # Good contrast for depth visualization
    
    # Toggle for scdepth specific postprocessing
    use_scdepth = False
    
    # Toggle to automatically normalize results for visualization
    normalize_for_display = True
    
    # Camera resolution for resizing
    target_resolution = (1280, 720)

    def __init__(self, inference_results, model_params, image=None):
        # Store model parameters first
        self._model_params = model_params
        
        # Call parent constructor with proper parameters
        super().__init__(inference_results, model_params, image)
        
        _resize_map = {
            'nearest': cv2.INTER_NEAREST,
            'bilinear': cv2.INTER_LINEAR,
            'area': cv2.INTER_AREA,
            'bicubic': cv2.INTER_CUBIC,
            'lanczos': cv2.INTER_LANCZOS4
        }

        # Retrieve the raw tensor from the inference
        data = self._inference_results[0]['data']
    
        # Dequantize if datatype is unsigned int or int
        if (data.dtype.kind == 'u' or data.dtype.kind == 'i'):
            data = dequantize(self._inference_results[0])

        data = data.squeeze(0)

        # Reshape raw output to model input dimensions
        hwc_layout = self._model_params.InputTensorLayout[0] == 'NHWC'
        if hwc_layout:
            shape_idxs = (0, 1)
        else:
            shape_idxs = (1, 2)

        if (data.shape[shape_idxs[0]] != self._model_params.InputH[0] or 
            data.shape[shape_idxs[1]] != self._model_params.InputW[0]):
            data = np.reshape(data.squeeze(),
                              (self._model_params.InputH[0], self._model_params.InputW[0], 1))
        
        # Fix tensor layout
        if not hwc_layout:
            data = np.transpose(data, (1, 2, 0))

        # Apply SCDepth postprocessing if needed
        if DepthResults.use_scdepth:
            data = 1 / (sigmoid(data) * 10 + 0.009)

        # Store both raw depth (for haptic analysis) and resized depth (for display)
        self.raw_depth = data.squeeze()  # Original model resolution for haptic processing
        
        # Resize for display/camera resolution if needed
        if self.image is not None:
            resize_mode = _resize_map.get(
                getattr(self._model_params, 'InputResizeMethod', ['bilinear'])[0], 
                cv2.INTER_LINEAR
            )
            data = cv2.resize(data, DepthResults.target_resolution, interpolation=resize_mode)
            data = np.expand_dims(data, axis=0)
        
        self._inference_results[0]['data'] = data

    @staticmethod
    def normalize_depth_map(depth_map):
        """Linear transform from [min, max] to [0.0, 1.0]"""
        depth_min, depth_max = depth_map.min(), depth_map.max()
        if depth_max == depth_min:
            return np.zeros_like(depth_map)
        return (depth_map - depth_min) / (depth_max - depth_min)
    
    def get_raw_depth_for_haptics(self):
        """Get the raw depth map at original model resolution for haptic processing."""
        return self.raw_depth
    
    def get_depth_at_coordinates(self, x, y):
        """Get depth value at specific pixel coordinates (x, y)."""
        h, w = self.raw_depth.shape
        if 0 <= x < w and 0 <= y < h:
            return self.raw_depth[y, x]
        return None
    
    def _convert_depth_to_image(self, depth_map):
        """Convert depth map to RGB image for visualization."""
        depth_map = depth_map.squeeze()
        
        if DepthResults.normalize_for_display:
            depth_map = self.normalize_depth_map(depth_map)
        
        depth_map = (depth_map * 255).astype(np.uint8)
        depth_map = cv2.applyColorMap(depth_map, DepthResults.color_map)
        return depth_map
    
    @property
    def image_overlay(self):
        """Generate visualization overlay."""
        image = self._convert_depth_to_image(self._inference_results[0]['data'])
        return image
