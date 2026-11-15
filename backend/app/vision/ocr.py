"""Optional local handwriting model. All candidates still require instructor review."""
import re
import threading


class LocalHandwritingOcr:
    model_id = 'microsoft/trocr-small-handwritten'

    def __init__(self):
        self._model = None
        self._processor = None
        self._lock = threading.Lock()
        self.last_text = None
        self.error = None

    def __call__(self, crop):
        try:
            with self._lock:
                import torch
                from PIL import Image
                from transformers import TrOCRProcessor, VisionEncoderDecoderModel
                if self._model is None:
                    self._processor = TrOCRProcessor.from_pretrained(self.model_id)
                    self._model = VisionEncoderDecoderModel.from_pretrained(self.model_id)
                    self._model.eval()
                pixels = self._processor(images=Image.fromarray(crop).convert('RGB'),return_tensors='pt').pixel_values
                with torch.inference_mode():
                    output = self._model.generate(pixels, max_new_tokens=8)
                text = self._processor.batch_decode(output,skip_special_tokens=True)[0].strip()
                self.error = None
                self.last_text = text
                # Confidence is deliberately conservative, not a calibrated probability.
                return (int(text), .5) if re.fullmatch('[1-5]',text) else (None,0.)
        except Exception as e:
            self.error = str(e)
            return None, 0.
