"""Resolve local IDREFs and cross-file href references."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from urllib.parse import unquote

from .parser import Element
from .registry import Registry

# RSA uses platform:/resource/<project>/path/to/file.emx#_id
_PLATFORM_PREFIX = "platform:/resource/"


class ResolveResult:
    __slots__ = ("element", "missing_file", "missing_id", "malformed")

    def __init__(
        self,
        element: Optional[Element] = None,
        missing_file: Optional[Path] = None,
        missing_id: Optional[str] = None,
        malformed: bool = False,
    ) -> None:
        self.element = element
        self.missing_file = missing_file  # Path that didn't exist on disk
        self.missing_id = missing_id      # ID not found in the resolved file
        self.malformed = malformed        # href couldn't be parsed at all

    @property
    def ok(self) -> bool:
        return self.element is not None


class Resolver:
    def __init__(self, registry: Registry) -> None:
        self._registry = registry
        self._cache: dict[tuple[Path, str], ResolveResult] = {}

    def resolve_idref(self, xmi_id: str) -> Optional[Element]:
        return self._registry.lookup_id(xmi_id)

    def resolve_href(self, href: str, source_file: Path) -> ResolveResult:
        cache_key = (source_file, href)
        if cache_key in self._cache:
            return self._cache[cache_key]
        result = self._do_resolve_href(href, source_file)
        self._cache[cache_key] = result
        return result

    def _do_resolve_href(self, href: str, source_file: Path) -> ResolveResult:
        if "#" not in href:
            return ResolveResult(malformed=True)

        file_part, id_part = href.split("#", 1)
        file_part = file_part.strip()
        id_part = id_part.strip()

        if not id_part:
            return ResolveResult(malformed=True)

        # Self-reference (same file)
        if not file_part:
            elem = self._registry.lookup_id(id_part)
            if elem:
                return ResolveResult(element=elem)
            return ResolveResult(missing_id=id_part)

        # Strip platform:/resource/<project>/ prefix
        if file_part.startswith(_PLATFORM_PREFIX):
            remainder = file_part[len(_PLATFORM_PREFIX):]
            # remainder is "<project>/path/to/file.emx" — drop the project segment
            parts = remainder.split("/", 1)
            file_part = parts[1] if len(parts) == 2 else parts[0]

        file_part = unquote(file_part)
        target_path = (source_file.parent / file_part).resolve()

        # Try to load the file if not already in registry
        if target_path not in self._registry.files:
            if not target_path.exists():
                return ResolveResult(missing_file=target_path)
            self._registry.load_file(target_path)

        emx = self._registry.files.get(target_path)
        if emx is None:
            return ResolveResult(missing_file=target_path)

        elem = emx.elements.get(id_part)
        if elem is None:
            return ResolveResult(missing_id=id_part)
        return ResolveResult(element=elem)
