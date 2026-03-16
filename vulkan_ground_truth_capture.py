import numpy as np
import os
import json
from datetime import datetime

class VulkanGroundTruth:
    """
    Helper to capture and metadata-tag tensors from working Vulkan workflows.
    These serves as the 'Gold Standard' for debugging the ROCm noise issues.
    """
    def __init__(self, output_dir="data/ground_truth/vulkan"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def save_tensor(self, name, tensor_data, metadata=None):
        """
        Saves a numpy array as the ground truth for a specific layer.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.npy"
        filepath = os.path.join(self.output_dir, filename)
        
        np.save(filepath, tensor_data)
        
        # Save metadata (shape, range, etc.)
        meta = {
            "name": name,
            "shape": list(tensor_data.shape),
            "dtype": str(tensor_data.dtype),
            "min": float(np.min(tensor_data)),
            "max": float(np.max(tensor_data)),
            "mean": float(np.mean(tensor_data)),
            "std": float(np.std(tensor_data)),
            "timestamp": timestamp
        }
        if metadata:
            meta.update(metadata)
            
        with open(filepath.replace(".npy", ".json"), "w") as f:
            json.dump(meta, f, indent=2)
            
        print(f"Stored ground truth for '{name}' to {filepath}")

if __name__ == "__main__":
    # Example usage:
    # gt = VulkanGroundTruth()
    # dummy_conv_output = np.random.randn(1, 64, 512, 512).astype(np.float32)
    # gt.save_tensor("unet_down_block_0_conv", dummy_conv_output, {"backend": "vulkan_ncnn"})
    print("Vulkan Ground Truth Capture tool ready.")
