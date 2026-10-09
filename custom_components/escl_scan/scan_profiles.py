"""Bounded eSCL setting profiles; relationships survive normalization."""
from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET

OUTPUT_FORMATS = ("application/pdf", "image/jpeg", "image/png")
DPI_MIN, DPI_MAX = 50, 1200


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def find(node: ET.Element, name: str) -> ET.Element | None:
    return next((el for el in node.iter() if local(el.tag) == name), None)


def values(node: ET.Element, name: str) -> tuple[str, ...] | None:
    result = tuple(dict.fromkeys(
        (el.text or "").strip() for el in node.iter()
        if local(el.tag) == name and (el.text or "").strip()
    ))
    if len(result) > 128 or any(len(item) > 256 for item in result):
        raise ValueError("scanner profile exceeds the supported size limit")
    return result or None


def number(node: ET.Element, name: str) -> int | None:
    el = find(node, name)
    try:
        return int(el.text) if el is not None and el.text else None
    except ValueError:
        return None


def _range(node: ET.Element | None) -> tuple[int, int, int] | None:
    if node is None:
        return None
    low, high = number(node, "Min"), number(node, "Max")
    step = number(node, "Step")
    if low is None or high is None or not 1 <= low <= high <= 9600:
        raise ValueError("invalid scanner resolution range")
    if step is not None and not 1 <= step <= 9600:
        raise ValueError("invalid scanner resolution step")
    return low, high, step or 1


@dataclass(frozen=True)
class SettingProfile:
    """None is unknown; an empty tuple is known but unusable by this client."""

    colors: tuple[str, ...] | None = None
    formats: tuple[str, ...] | None = None
    extended_formats: tuple[str, ...] | None = None
    resolutions: tuple[int, ...] | None = None

    def public(self) -> dict:
        return {
            "colors": [color for color, mode in (("color", "RGB24"), ("gray", "Grayscale8"))
                       if mode in self.colors] if self.colors is not None else None,
            "formats": [fmt for fmt in OUTPUT_FORMATS if fmt in self.formats]
            if self.formats is not None else None,
            "resolutions": list(self.resolutions) if self.resolutions is not None else None,
        }


def parse_profiles(root: ET.Element, source: ET.Element) -> list[SettingProfile]:
    """Resolve named profiles without namespace coupling or unbounded recursion."""
    named = {el.attrib["name"]: el for el in root.iter()
             if local(el.tag) == "SettingProfile" and el.attrib.get("name")}
    nodes = [el for el in source.iter() if local(el.tag) == "SettingProfile"]
    if len(nodes) > 64 or len(named) > 128:
        raise ValueError("too many scanner setting profiles")
    result = []
    for node in nodes or [source]:
        seen = set()
        while ref := node.attrib.get("ref"):
            if ref in seen or len(seen) >= 8 or ref not in named:
                raise ValueError("unresolved or cyclic scanner setting profile")
            seen.add(ref)
            node = named[ref]
        extended = values(node, "DocumentFormatExt")
        standard = values(node, "DocumentFormat")
        formats = tuple(dict.fromkeys((standard or ()) + (extended or ())))
        discrete = [el for el in node.iter() if local(el.tag) == "DiscreteResolution"]
        supported = set()
        for el in discrete:
            x, y = number(el, "XResolution"), number(el, "YResolution")
            if x is not None and DPI_MIN <= x <= DPI_MAX and (y is None or x == y):
                supported.add(x)
        xr, yr = _range(find(node, "XResolutionRange")), _range(find(node, "YResolutionRange"))
        if xr is not None and yr is not None:
            for dpi in range(DPI_MIN, DPI_MAX + 1):
                if all(low <= dpi <= high and (dpi - low) % step == 0
                       for low, high, step in (xr, yr)):
                    supported.add(dpi)
        known_resolution = bool(discrete) or xr is not None or yr is not None
        result.append(SettingProfile(
            colors=values(node, "ColorMode"), formats=formats or None,
            extended_formats=extended,
            resolutions=tuple(sorted(supported)) if known_resolution else None,
        ))
    return result


@dataclass(frozen=True)
class ScanSelection:
    dpi: int
    document_format: str
    format_extension: bool


def select_profile(profiles: list[SettingProfile], color: str, dpi: int) -> ScanSelection:
    mode = "Grayscale8" if color == "gray" else "RGB24"
    choices = []
    for profile in profiles:
        if profile.colors is not None and mode not in profile.colors:
            continue
        resolutions = profile.resolutions if profile.resolutions is not None else (dpi,)
        if not resolutions:
            continue
        selected_dpi = min(resolutions, key=lambda value: (abs(value - dpi), value))
        for preference, fmt in enumerate(OUTPUT_FORMATS):
            if profile.formats is not None and fmt not in profile.formats:
                continue
            # Unknown format metadata retains the historical PDF request.
            if profile.formats is None and fmt != "application/pdf":
                continue
            extension = profile.formats is None or fmt in (profile.extended_formats or ())
            choices.append((preference, abs(selected_dpi - dpi), selected_dpi, fmt, extension))
    if not choices:
        raise ValueError(
            "scanner does not support this color, resolution and document format combination")
    _, _, selected_dpi, fmt, extension = min(choices)
    return ScanSelection(selected_dpi, fmt, extension)
