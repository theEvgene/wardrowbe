import asyncio
from pathlib import Path
from typing import Any

from PIL import Image

from app.services.garment_identity_service import EmbeddingResult

DINO_MODEL_ID = "facebook/dinov2-small"
DINO_MODEL_REVISION = "ed25f3a31f01632728cabb09d1542f84ab7b0056"
DINO_PREPROCESS_REVISION = "transformers-4.52.3-slow-image-processor-v1"


class Dinov2EmbeddingProvider:
    model = DINO_MODEL_ID
    model_revision = DINO_MODEL_REVISION
    preprocess_revision = DINO_PREPROCESS_REVISION

    def __init__(self) -> None:
        self._processor: Any | None = None
        self._model_instance: Any | None = None
        self._load_lock = asyncio.Lock()
        self._inference_lock = asyncio.Lock()

    async def embed(self, image_path: Path) -> EmbeddingResult:
        await self._ensure_loaded()
        # The arq pool can run several jobs concurrently; serialize this CPU-heavy
        # model so bulk uploads do not multiply peak RAM and CPU contention.
        async with self._inference_lock:
            return await asyncio.to_thread(self._embed_sync, image_path)

    async def _ensure_loaded(self) -> None:
        if self._processor is not None and self._model_instance is not None:
            return
        async with self._load_lock:
            if self._processor is None or self._model_instance is None:
                await asyncio.to_thread(self._load_sync)

    def _load_sync(self) -> None:
        from transformers import AutoImageProcessor, AutoModel

        self._processor = AutoImageProcessor.from_pretrained(
            self.model,
            revision=self.model_revision,
            local_files_only=True,
            use_fast=False,
        )
        self._model_instance = AutoModel.from_pretrained(
            self.model,
            revision=self.model_revision,
            local_files_only=True,
        )
        self._model_instance.eval()

    def _embed_sync(self, image_path: Path) -> EmbeddingResult:
        import torch

        if self._processor is None or self._model_instance is None:
            raise RuntimeError("DINOv2 provider is not loaded")
        with Image.open(image_path) as image:
            inputs = self._processor(images=image.convert("RGB"), return_tensors="pt")
        with torch.inference_mode():
            outputs = self._model_instance(**inputs)
        cls_embedding = outputs.last_hidden_state[0, 0].detach().cpu().float().tolist()
        return EmbeddingResult(vector=cls_embedding)
