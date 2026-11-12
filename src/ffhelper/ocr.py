"""Fast OCR for short UI text such as boss cast names."""

from __future__ import annotations

import cv2
import numpy as np
from rapidocr import RapidOCR


class TextReader:
    def __init__(self, threads: int = 2):
        self._engine = RapidOCR(
            params={
                "Global.log_level": "error",
                "Global.use_cls": False,
                # The defaults upscale thin crops ~15x (~400 ms a read); capping keeps reads ~20 ms.
                "Det.limit_type": "max",
                "Det.limit_side_len": 960,
                # Leave CPU headroom for the game.
                "EngineConfig.onnxruntime.intra_op_num_threads": threads,
            }
        )
        # Models load lazily, and recognition only runs when text is found, so read a word up front.
        warm_up = np.zeros((48, 160, 3), np.uint8)
        cv2.putText(warm_up, "Ready", (8, 34), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        self.read(warm_up)

    def read(self, image: np.ndarray) -> list[str]:
        """Lines of text found in a BGR image."""
        return [text for text in (self._engine(image).txts or ()) if text.strip()]
