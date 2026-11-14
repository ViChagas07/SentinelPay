import re
from typing import Any

import cv2
import numpy as np
import pymupdf

from paysentineliq.application.errors import InvalidDocumentError
from paysentineliq.domain.ingestion import BBox, VisualSignal

_DISCLAIMER = "Heuristic signal, not proof."
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class VisualAnomalyService:
    def analyze_image(
        self,
        image: bytes,
        *,
        page: int,
    ) -> tuple[VisualSignal, ...]:
        if not image:
            raise InvalidDocumentError()

        buffer = np.frombuffer(image, dtype=np.uint8)
        bgr = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if bgr is None:
            raise InvalidDocumentError()

        height, width = bgr.shape[:2]
        if width <= 0 or height <= 0:
            raise InvalidDocumentError()

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        signals: list[VisualSignal] = []

        resolution = _clamp(1.0 - min(width, height) / 1000.0)
        signals.append(
            _signal(
                "image_resolution",
                resolution,
                f"Image is {width}x{height}; lower resolution can hide detail.",
                page,
            )
        )

        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        laplacian_variance = float(laplacian.var())
        blur = _clamp(1.0 - laplacian_variance / 250.0)
        signals.append(
            _signal(
                "image_blur",
                blur,
                f"Laplacian variance is {laplacian_variance:.2f}; lower means blurrier.",
                page,
            )
        )

        median = cv2.medianBlur(gray, 3)
        residual = gray.astype(np.float64) - median.astype(np.float64)
        noise = _clamp(float(residual.std()) / 20.0)
        signals.append(
            _signal(
                "image_noise",
                noise,
                f"Residual noise standard deviation is {float(residual.std()):.2f}.",
                page,
            )
        )

        ela_grid = _ela_blocks(bgr)
        ela_index = _max_index(ela_grid)
        ela_region = _block_region(ela_grid.shape, ela_index, width, height)
        ela_value = _clamp(float(ela_grid[ela_index]) / 15.0)
        signals.append(
            _signal(
                "ela_recompression",
                ela_value,
                f"Maximum JPEG recompression difference is {float(ela_grid[ela_index]):.2f}.",
                page,
                ela_region,
            )
        )

        noise_grid = _noise_blocks(laplacian)
        noise_index = _max_index(noise_grid)
        noise_region = _block_region(
            noise_grid.shape,
            noise_index,
            width,
            height,
        )
        noise_median = float(np.median(noise_grid))
        noise_max = float(noise_grid[noise_index])
        noise_variance = _clamp(max(0.0, noise_max - noise_median - 30.0) / 100.0)
        signals.append(
            _signal(
                "noise_variance_blocks",
                noise_variance,
                f"Max block noise {noise_max:.2f} vs median {noise_median:.2f}.",
                page,
                noise_region,
            )
        )

        copy_value, copy_region = _copy_move(gray, width, height)
        signals.append(
            _signal(
                "copy_move_orb",
                copy_value,
                "ORB keypoints with repeated geometry inside the page.",
                page,
                copy_region,
            )
        )

        return tuple(signals)

    def analyze_pdf_metadata(
        self,
        pdf: bytes,
    ) -> tuple[VisualSignal, ...]:
        if not pdf:
            raise InvalidDocumentError()

        try:
            document = pymupdf.open(stream=pdf, filetype="pdf")
        except Exception as exc:
            raise InvalidDocumentError() from exc

        try:
            metadata = document.metadata or {}
        finally:
            document.close()

        producer = _safe_text(metadata.get("producer"))
        creator = _safe_text(metadata.get("creator"))
        creation_date = _safe_text(metadata.get("creationDate"))
        modification_date = _safe_text(metadata.get("modDate"))

        has_producer = bool(producer or creator)
        signals: list[VisualSignal] = [
            _signal(
                "pdf_producer",
                0.1 if has_producer else 0.4,
                f"Producer='{producer}'; Creator='{creator}'.",
            ),
            _signal(
                "pdf_dates",
                0.05 if creation_date and modification_date else 0.3,
                f"creationDate='{creation_date}'; modDate='{modification_date}'.",
            ),
        ]

        incremental = b"/Prev" in pdf or pdf.count(b"%%EOF") > 1
        signals.append(
            _signal(
                "pdf_incremental_updates",
                1.0 if incremental else 0.0,
                "Incremental update markers found."
                if incremental
                else "No incremental update markers found.",
            )
        )

        layers = b"/OCProperties" in pdf or b"/OCGs" in pdf
        signals.append(
            _signal(
                "pdf_overlaid_layers",
                1.0 if layers else 0.0,
                "Optional content/overlaid layers found."
                if layers
                else "No optional content layers found.",
            )
        )

        return tuple(signals)


def _signal(
    name: str,
    value: float,
    explanation: str,
    page: int | None = None,
    region: BBox | None = None,
) -> VisualSignal:
    return VisualSignal(
        name=name,
        value=_clamp(value),
        explanation=f"{explanation} {_DISCLAIMER}",
        page=page,
        region=region,
    )


def _ela_blocks(image: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    success, encoded = cv2.imencode(
        ".jpg",
        image,
        [int(cv2.IMWRITE_JPEG_QUALITY), 90],
    )
    if not success:
        raise InvalidDocumentError()
    recompressed = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if recompressed is None:
        raise InvalidDocumentError()

    difference = np.abs(image.astype(np.float64) - recompressed.astype(np.float64)).mean(axis=2)
    return _block_grid(difference, 16)


def _noise_blocks(
    laplacian: np.ndarray[Any, Any],
) -> np.ndarray[Any, Any]:
    return _block_grid(np.abs(laplacian), 32)


def _block_grid(
    values: np.ndarray[Any, Any],
    block_size: int,
) -> np.ndarray[Any, Any]:
    height, width = values.shape[:2]
    grid_width = max(1, width // block_size)
    grid_height = max(1, height // block_size)
    return cv2.resize(
        values,
        (grid_width, grid_height),
        interpolation=cv2.INTER_AREA,
    )


def _max_index(grid: np.ndarray[Any, Any]) -> tuple[int, ...]:
    return tuple(
        int(index)
        for index in np.unravel_index(
            int(np.argmax(grid)),
            grid.shape,
        )
    )


def _block_region(
    grid_shape: tuple[int, ...],
    index: tuple[int, ...],
    width: int,
    height: int,
) -> BBox:
    grid_height, grid_width = grid_shape[:2]
    block_width = width / grid_width
    block_height = height / grid_height
    row, column = index[:2]
    return (
        column * block_width,
        row * block_height,
        min(width, (column + 1) * block_width),
        min(height, (row + 1) * block_height),
    )


def _copy_move(
    gray: np.ndarray[Any, Any],
    width: int,
    height: int,
) -> tuple[float, BBox | None]:
    orb = cv2.ORB_create(nfeatures=1000)  # type: ignore[attr-defined]
    keypoints, descriptors = orb.detectAndCompute(gray, None)
    if descriptors is None or len(keypoints) < 10:
        return 0.0, None

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    groups = matcher.knnMatch(descriptors, descriptors, k=3)
    clusters: dict[tuple[float, float], list[tuple[float, float]]] = {}

    for group in groups:
        for match in group:
            if match.queryIdx == match.trainIdx:
                continue
            if match.distance > 30:
                continue
            first = keypoints[match.queryIdx].pt
            second = keypoints[match.trainIdx].pt
            delta_x = second[0] - first[0]
            delta_y = second[1] - first[1]
            distance = (delta_x**2 + delta_y**2) ** 0.5
            if distance < 80:
                continue
            key = (
                round(delta_x / 25.0) * 25,
                round(delta_y / 25.0) * 25,
            )
            clusters.setdefault(key, []).extend([first, second])

    if not clusters:
        return 0.0, None

    points = max(clusters.values(), key=len)
    match_count = len(points) // 2
    if match_count < 50:
        return 0.0, None

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    region = (
        max(0.0, min(xs)),
        max(0.0, min(ys)),
        min(float(width), max(xs)),
        min(float(height), max(ys)),
    )
    return _clamp((match_count - 40) / 100.0), region


def _safe_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    clean = _CONTROL_CHARS.sub("", value).replace("<", "").replace(">", "")
    return clean.strip()[:80]


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
