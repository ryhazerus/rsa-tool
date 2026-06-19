"""Validate xmi:id uniqueness and presence."""

from __future__ import annotations

from typing import Iterator

from .base import BaseValidator, Issue, Severity

# UML types that must carry xmi:id
_MUST_HAVE_ID = {
    "uml:Package", "uml:Model",
    "uml:Class", "uml:Interface", "uml:Component", "uml:DataType",
    "uml:Enumeration", "uml:PrimitiveType", "uml:Signal",
    "uml:Association", "uml:AssociationClass",
    "uml:Generalization", "uml:InterfaceRealization",
    "uml:Dependency", "uml:Usage", "uml:Realization",
    "uml:Property", "uml:Operation", "uml:Parameter",
    "uml:Collaboration", "uml:Interaction",
}


class IdValidator(BaseValidator):
    def validate(self, registry, resolver) -> Iterator[Issue]:
        yield from self._duplicate_in_file(registry)
        yield from self._duplicate_cross_file(registry)
        yield from self._missing_id(registry)

    def _duplicate_in_file(self, registry) -> Iterator[Issue]:
        for emx in registry.files.values():
            for xmi_id, line1, line2 in emx.duplicate_ids:
                yield Issue(
                    severity=Severity.ERROR,
                    rule="ids.DUPLICATE_ID_IN_FILE",
                    file_path=emx.path,
                    line=line2,
                    element_id=xmi_id,
                    element_name="",
                    message=f"xmi:id '{xmi_id}' defined again at line {line2} (first at line {line1})",
                )

    def _duplicate_cross_file(self, registry) -> Iterator[Issue]:
        for elems in registry.cross_file_duplicates():
            files_str = ", ".join(str(e.file_path.name) for e in elems)
            for elem in elems:
                yield Issue(
                    severity=Severity.ERROR,
                    rule="ids.DUPLICATE_ID_CROSS_FILE",
                    file_path=elem.file_path,
                    line=elem.line,
                    element_id=elem.xmi_id,
                    element_name=elem.name,
                    message=f"xmi:id '{elem.xmi_id}' also exists in: {files_str}",
                )

    def _missing_id(self, registry) -> Iterator[Issue]:
        for emx in registry.files.values():
            for xmi_type, name, line in emx.missing_ids:
                if xmi_type not in _MUST_HAVE_ID:
                    continue
                yield Issue(
                    severity=Severity.ERROR,
                    rule="ids.MISSING_ID",
                    file_path=emx.path,
                    line=line,
                    element_id="",
                    element_name=name,
                    message=f"{xmi_type} element '{name}' is missing xmi:id",
                )
