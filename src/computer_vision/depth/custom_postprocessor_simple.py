"""
Simplified custom depth postprocessor for haptic feedback vest system.
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
    Simplified custom depth postprocessor optimized for haptic feedback.
    """
    
    # Color map for visualization
    color_map = cv2.COLORMAP_TURBO
    
    # Toggle for scdepth specific postprocessing
    use_scdepth = False
    
    # Camera resolution for resizing
    target_resolution = (1280, 720)

    def __init__(self, inference_results, model_params, image=None):
        # Call parent constructor
        super().__init__(inference_results, model_params, image)
        
        # Store the raw depth for haptic processing
        self._process_depth_data()
    
    def _process_depth_data(self):
        """Process the depth data."""
        try:
            # Get the raw tensor
            data = self._inference_results[0]['data']
        
            # Dequantize if needed
            if (data.dtype.kind == 'u' or data.dtype.kind == 'i'):
                data = dequantize(self._inference_results[0])

            # Remove batch dimension if present
            if len(data.shape) > 2:
                data = data.squeeze()

            # Apply SCDepth postprocessing if needed
            if DepthResults.use_scdepth:
                data = 1 / (sigmoid(data) * 10 + 0.009)

            # Store the raw depth at model resolution for haptic processing
            self.raw_depth = data

            # For visualization, resize and prepare
            if self.image is not None:
                display_data = cv2.resize(data, DepthResults.target_resolution, interpolation=cv2.INTER_LINEAR)
                self._inference_results[0]['data'] = np.expand_dims(display_data, axis=0)
            else:
                self._inference_results[0]['data'] = np.expand_dims(data, axis=0)
                
        except Exception as e:
            print(f"Error in depth postprocessor: {e}")
            # Create fallback data
            self.raw_depth = np.ones((256, 320)) * 5.0  # Default depth
            self._inference_results[0]['data'] = np.expand_dims(self.raw_depth, axis=0)
    
    def get_raw_depth_for_haptics(self):
        """Get the raw depth map at original model resolution for haptic processing."""
        return self.raw_depth
    
    @staticmethod
    def normalize_depth_map(depth_map):
        """Linear transform from [min, max] to [0.0, 1.0]"""
        depth_min, depth_max = depth_map.min(), depth_map.max()
        if depth_max == depth_min:
            return np.zeros_like(depth_map)
        return (depth_map - depth_min) / (depth_max - depth_min)
    
    def _convert_depth_to_image(self, depth_map):
        """Convert depth map to RGB image for visualization."""
        depth_map = depth_map.squeeze()
        
        # Normalize for display
        depth_map = self.normalize_depth_map(depth_map)
        
        depth_map = (depth_map * 255).astype(np.uint8)
        depth_map = cv2.applyColorMap(depth_map, DepthResults.color_map)
        return depth_map
    
    @property
    def image_overlay(self):
        """Generate visualization overlay."""
        image = self._convert_depth_to_image(self._inference_results[0]['data'])
        return image
