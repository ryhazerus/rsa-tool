"""Cross-file registry: merges EmxFile objects and provides lookup."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Optional

from .parser import Element, EmxFile, RefSite, parse_file


class Registry:
    def __init__(self) -> None:
        self.files: dict[Path, EmxFile] = {}
        # xmi_id → list of Elements (from any file; len > 1 means cross-file duplicate)
        self._id_index: dict[str, list[Element]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_file(self, path: Path) -> EmxFile:
        path = path.resolve()
        if path in self.files:
            return self.files[path]
        emx = parse_file(path)
        self.files[path] = emx
        for elem in emx.elements.values():
            self._id_index[elem.xmi_id].append(elem)
        return emx

    def load_directory(self, root: Path, recursive: bool = True) -> None:
        pattern = "**/*.emx" if recursive else "*.emx"
        for p in sorted(root.glob(pattern)):
            self.load_file(p)

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def lookup_id(self, xmi_id: str) -> Optional[Element]:
        """Return any single Element with this ID (None if not found)."""
        hits = self._id_index.get(xmi_id)
        return hits[0] if hits else None

    def lookup_id_all(self, xmi_id: str) -> list[Element]:
        """All Elements with this ID across all files."""
        return self._id_index.get(xmi_id, [])

    def all_elements(self):
        for emx in self.files.values():
            yield from emx.elements.values()

    def all_refs(self):
        for emx in self.files.values():
            yield from emx.refs

    def cross_file_duplicates(self) -> list[list[Element]]:
        return [elems for elems in self._id_index.values() if len(elems) > 1]
