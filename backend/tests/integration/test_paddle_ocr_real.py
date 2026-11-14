import os
import time

import psutil
import pytest

from paysentineliq.infrastructure.ocr.paddle import PaddleOcrAdapter
from tests.support.synthetic import clean_image_bytes

pytestmark = [
    pytest.mark.integration,
    pytest.mark.docker,
    pytest.mark.skipif(
        os.environ.get("RUN_REAL_OCR") != "1",
        reason="set RUN_REAL_OCR=1 to run the real PaddleOCR model",
    ),
]


async def test_real_paddleocr_reads_synthetic_text() -> None:
    image = clean_image_bytes()
    process = psutil.Process()
    memory_before = process.memory_info().rss
    started = time.perf_counter()

    result = await PaddleOcrAdapter(languages=("en",)).recognize(image)

    elapsed = time.perf_counter() - started
    memory_after = process.memory_info().rss
    text = " ".join(block.text for block in result.blocks).upper()

    print(
        f"REAL_OCR elapsed_s={elapsed:.2f} "
        f"rss_delta_mb={(memory_after - memory_before) / 1024 / 1024:.1f} "
        f"blocks={len(result.blocks)}"
    )
    assert result.blocks
    assert any(token in text for token in ("PAYSENTINELIQ", "SYNTHETIC", "ACCOUNT"))
