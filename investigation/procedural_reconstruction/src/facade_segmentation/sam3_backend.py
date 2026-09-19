"""SAM 3 adapter. Heavy dependencies are loaded only on construction."""
from pathlib import Path
import numpy as np


class Sam3Backend:
    def __init__(self, checkpoint: Path, confidence: float = .5):
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be in [0,1]")
        import torch
        from sam3.model_builder import build_sam3_image_model
        from sam3.model.sam3_image_processor import Sam3Processor
        if not torch.cuda.is_available():
            raise RuntimeError("GPU requerida: ejecuta dentro de una asignación Slurm")
        self.torch = torch
        model = build_sam3_image_model(checkpoint_path=str(checkpoint),
                                      load_from_HF=False, device="cuda", eval_mode=True)
        self.processor = Sam3Processor(model, confidence_threshold=confidence)

    def predict(self, image, prompt: str):
        if not prompt.strip():
            raise ValueError("prompt cannot be empty")
        with self.torch.inference_mode():
            state = self.processor.set_image(image)
            result = self.processor.set_text_prompt(state=state, prompt=prompt)
            masks = result['masks'].detach().cpu().numpy()
            scores = result['scores'].detach().cpu().numpy().reshape(-1)
        if masks.ndim == 4 and masks.shape[1] == 1:
            masks = masks[:, 0]
        if masks.shape != (len(scores), image.height, image.width):
            raise RuntimeError(f"Unexpected SAM3 mask shape: {masks.shape}")
        return masks.astype(np.bool_), scores
