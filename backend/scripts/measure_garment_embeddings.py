import argparse
import asyncio
import json
import math
import time
from pathlib import Path

from app.services.dinov2_embedding import Dinov2EmbeddingProvider


async def measure(image_paths: list[Path]) -> dict:
    provider = Dinov2EmbeddingProvider()
    vectors: list[list[float]] = []
    durations: list[float] = []
    for image_path in image_paths:
        started_at = time.perf_counter()
        result = await provider.embed(image_path)
        durations.append(time.perf_counter() - started_at)
        magnitude = math.sqrt(sum(value * value for value in result.vector))
        vectors.append([value / magnitude for value in result.vector])

    similarities = []
    for left_index, left in enumerate(vectors):
        for right_index in range(left_index + 1, len(vectors)):
            right = vectors[right_index]
            similarities.append(
                {
                    "left": str(image_paths[left_index]),
                    "right": str(image_paths[right_index]),
                    "cosine_similarity": sum(a * b for a, b in zip(left, right, strict=True)),
                }
            )

    return {
        "model": provider.model,
        "model_revision": provider.model_revision,
        "preprocess_revision": provider.preprocess_revision,
        "dimensions": [len(vector) for vector in vectors],
        "durations_seconds": durations,
        "similarities": similarities,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("images", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(measure(args.images)), indent=2))


if __name__ == "__main__":
    main()
