"""Compatibility regressions use synthetic input unless explicitly attributed."""
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
import pytest

from custom_components.escl_scan.coordinator import _PdfFileWriter
from custom_components.escl_scan.scanner import parse_scanner_capabilities, scanner_quirks

FIXTURES = Path(__file__).parent / "fixtures"


def test_profile_membership_prevents_cross_profile_combinations():
    caps = parse_scanner_capabilities((FIXTURES / "profiles-disjoint.xml").read_bytes())
    selected = caps.select_options("Platen", "color", False, 600)
    assert selected.dpi == 300
    assert selected.document_format == "application/pdf"
    assert selected.format_extension is False
    gray = caps.select_options("Platen", "gray", False, 600)
    assert gray.dpi == 600 and gray.document_format == "image/png"
    assert gray.format_extension is True


def test_named_profile_and_intersecting_ranges():
    caps = parse_scanner_capabilities((FIXTURES / "profiles-reference-range.xml").read_bytes())
    assert caps.source_resolutions["Platen"] == [200, 300, 400, 500]
    assert caps.select_options("Platen", "color", False, 275).dpi == 300
    assert caps.select_options("Platen", "color", False, 600).dpi == 500
    with pytest.raises(ValueError, match="does not support"):
        caps.select_options("Platen", "gray", False, 300)


@pytest.mark.parametrize("profile", [
    '<SettingProfile ref="missing"/>',
    '<SettingProfile name="loop" ref="loop"/>',
])
def test_invalid_references_are_bounded(profile):
    with pytest.raises(ValueError, match="profile"):
        parse_scanner_capabilities(
            (
                f"<ScannerCapabilities><PlatenInputCaps>{profile}</PlatenInputCaps>"
                "</ScannerCapabilities>"
            ).encode()
        )


def test_asymmetric_only_is_known_incompatible():
    caps = parse_scanner_capabilities(
        b"<ScannerCapabilities><PlatenInputCaps><DiscreteResolution>"
        b"<XResolution>300</XResolution><YResolution>600</YResolution>"
        b"</DiscreteResolution></PlatenInputCaps></ScannerCapabilities>"
    )
    assert caps.setting_profiles["Platen"][0].resolutions == ()
    with pytest.raises(ValueError, match="combination"):
        caps.select_options("Platen", "color", False, 300)


def test_unknown_profile_retains_pdf_and_requested_dpi():
    caps = parse_scanner_capabilities(
        b"<ScannerCapabilities><PlatenInputCaps/></ScannerCapabilities>"
    )
    choice = caps.select_options("Platen", "color", False, 275)
    assert choice.dpi == 275 and choice.document_format == "application/pdf"
    assert choice.format_extension


def test_letter_region_honors_centered_feeder_and_bounds():
    caps = parse_scanner_capabilities(
        b"<ScannerCapabilities><Adf><AdfSimplexInputCaps><MaxWidth>2600</MaxWidth>"
        b"<MaxHeight>4200</MaxHeight></AdfSimplexInputCaps><Justification>"
        b"<XImagePosition>Center</XImagePosition></Justification></Adf></ScannerCapabilities>"
    )
    assert caps.select_region("Feeder", False, "letter") == (2550, 3300, 25, 0)
    with pytest.raises(ValueError, match="outside"):
        caps.select_region("Feeder", False, "custom", 2700, 3000)


@pytest.mark.parametrize("fmt,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg")])
def test_image_conversion_preserves_physical_dimensions(tmp_path, fmt, mime):
    path = tmp_path / "page"
    with Image.new("RGB", (300, 600), "white") as image:
        image.save(path, fmt)
    writer = _PdfFileWriter(path)
    writer.convert_image(mime, 300)
    assert writer.is_valid_pdf()
    page = PdfReader(path).pages[0]
    assert tuple(map(float, page.mediabox)) == (0, 0, 72, 144)
    assert not path.with_name("page.image-pdf").exists()


def test_image_conversion_rejects_mismatched_type_and_size(tmp_path, monkeypatch):
    path = tmp_path / "page"
    with Image.new("RGB", (20, 20)) as image:
        image.save(path, "PNG")
    writer = _PdfFileWriter(path)
    with pytest.raises(ValueError, match="unexpected"):
        writer.convert_image("image/jpeg", 300)
    monkeypatch.setattr("custom_components.escl_scan.coordinator.MAX_IMAGE_PIXELS", 100)
    with pytest.raises(ValueError, match="megapixel"):
        writer.convert_image("image/png", 300)


def test_quirks_are_narrowly_scoped():
    assert scanner_quirks("B205") == ("retry_missing_document",)
    assert scanner_quirks("Brother MFC-L2710DW") == ("next_page_delay",)
    assert scanner_quirks("RICOH") == ("status_before_load",)
    assert not scanner_quirks("HP Color LaserJet M283fdw")
    assert not scanner_quirks("Xerox Other")


def test_real_redacted_hp_fixture_keeps_native_pdf_and_duplex_independent():
    caps = parse_scanner_capabilities((FIXTURES / "hp-m283fdw-capabilities.xml").read_bytes())
    assert not caps.adf_duplex
    for source in ("Platen", "Feeder"):
        selected = caps.select_options(source, "color", False, 300)
        assert selected.document_format == "application/pdf" and selected.dpi == 300
        assert selected.format_extension


def test_partial_profiles_keep_public_summaries_unknown():
    from unittest.mock import AsyncMock

    from custom_components.escl_scan.capabilities import capability_snapshot
    from custom_components.escl_scan.capability_cache import CapabilityCache
    from custom_components.escl_scan.scan_profiles import SettingProfile
    from custom_components.escl_scan.scanner import ScannerCapabilities
    cache = CapabilityCache(AsyncMock())
    cache.value = ScannerCapabilities(
        setting_profiles={"Platen": [SettingProfile(colors=("RGB24",), resolutions=(300,)),
                                     SettingProfile()]},
        source_resolutions={"Platen": [300]}, source_color_modes={"Platen": ["RGB24"]})
    profile = capability_snapshot(cache, None)["supported"]["profiles"]["Platen"]
    assert profile["resolutions"] is None and profile["colors"] is None
    assert profile["combinations"][0]["resolutions"] == [300]
