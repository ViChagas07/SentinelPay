import pytest

from paysentineliq.application.errors import InvalidDocumentError
from paysentineliq.domain.ingestion import VisualSignal
from paysentineliq.infrastructure.vision.visual_anomalies import (
    VisualAnomalyService,
)
from tests.support.synthetic import (
    blurred_image_bytes,
    clean_image_bytes,
    native_pdf_bytes,
    pasted_image_bytes,
    pdf_with_incremental_marker,
    pdf_with_layers_marker,
    small_image_bytes,
)

pytestmark = pytest.mark.unit

_IMAGE_SIGNAL_NAMES = {
    "image_resolution",
    "image_blur",
    "image_noise",
    "ela_recompression",
    "noise_variance_blocks",
    "copy_move_orb",
}
_PDF_SIGNAL_NAMES = {
    "pdf_producer",
    "pdf_dates",
    "pdf_incremental_updates",
    "pdf_overlaid_layers",
}


def _signals(image: bytes) -> dict[str, VisualSignal]:
    signals = VisualAnomalyService().analyze_image(image, page=3)
    return {signal.name: signal for signal in signals}


def test_clean_image_returns_all_signals_and_heuristic_disclaimer() -> None:
    signals = _signals(clean_image_bytes())

    assert set(signals) == _IMAGE_SIGNAL_NAMES
    for signal in signals.values():
        assert 0.0 <= signal.value <= 1.0
        assert "Heuristic signal, not proof." in signal.explanation
        assert signal.page == 3
    assert signals["image_resolution"].value == 0.0
    assert signals["copy_move_orb"].value == 0.0


def test_blurred_fixture_raises_blur_signal() -> None:
    clean = _signals(clean_image_bytes())
    blurred = _signals(blurred_image_bytes())

    assert blurred["image_blur"].value > clean["image_blur"].value
    assert blurred["image_blur"].value > 0.8


def test_small_fixture_raises_resolution_signal() -> None:
    clean = _signals(clean_image_bytes())
    small = _signals(small_image_bytes())

    assert small["image_resolution"].value > clean["image_resolution"].value
    assert small["image_resolution"].value > 0.5


def test_pasted_fixture_raises_copy_move_and_compression_signals() -> None:
    clean = _signals(clean_image_bytes())
    pasted = _signals(pasted_image_bytes())

    assert pasted["copy_move_orb"].value > clean["copy_move_orb"].value
    assert pasted["copy_move_orb"].value > 0.2
    assert pasted["copy_move_orb"].region is not None
    assert pasted["ela_recompression"].value > clean["ela_recompression"].value
    assert pasted["noise_variance_blocks"].value > clean["noise_variance_blocks"].value
    assert pasted["image_noise"].value > clean["image_noise"].value


def test_native_pdf_metadata_signals() -> None:
    signals = {
        signal.name: signal
        for signal in VisualAnomalyService().analyze_pdf_metadata(native_pdf_bytes())
    }

    assert set(signals) == _PDF_SIGNAL_NAMES
    assert signals["pdf_producer"].value <= 0.1
    assert signals["pdf_dates"].value <= 0.05
    assert signals["pdf_incremental_updates"].value == 0.0
    assert signals["pdf_overlaid_layers"].value == 0.0
    assert all("Heuristic signal, not proof." in signal.explanation for signal in signals.values())


def test_pdf_incremental_and_layers_markers_are_detected() -> None:
    incremental = {
        signal.name: signal
        for signal in VisualAnomalyService().analyze_pdf_metadata(pdf_with_incremental_marker())
    }
    layers = {
        signal.name: signal
        for signal in VisualAnomalyService().analyze_pdf_metadata(pdf_with_layers_marker())
    }

    assert incremental["pdf_incremental_updates"].value == 1.0
    assert incremental["pdf_overlaid_layers"].value == 0.0
    assert layers["pdf_overlaid_layers"].value == 1.0
    assert layers["pdf_incremental_updates"].value == 0.0


def test_invalid_image_and_pdf_are_rejected() -> None:
    service = VisualAnomalyService()

    with pytest.raises(InvalidDocumentError):
        service.analyze_image(b"not an image", page=1)
    with pytest.raises(InvalidDocumentError):
        service.analyze_pdf_metadata(b"not a pdf")
