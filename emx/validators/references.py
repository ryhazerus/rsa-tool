"""Validate all IDREF and href references."""

from __future__ import annotations

from typing import Iterator

from ..parser import IDREF_ATTRS
from .base import BaseValidator, Issue, Severity

# For these attributes, the resolved target must be a Classifier-like type
_TYPE_ATTR_EXPECTED = {
    "type": {
        "uml:Class", "uml:Interface", "uml:DataType", "uml:PrimitiveType",
        "uml:Enumeration", "uml:Signal", "uml:Component",
    },
    "contract": {"uml:Interface"},
    "general": {
        "uml:Class", "uml:Interface", "uml:Component",
        "uml:DataType", "uml:Enumeration",
    },
}


class ReferenceValidator(BaseValidator):
    def validate(self, registry, resolver) -> Iterator[Issue]:
        for ref in registry.all_refs():
            if ref.is_href:
                yield from self._check_href(ref, resolver)
            else:
                yield from self._check_idref(ref, resolver)

    def _check_href(self, ref, resolver) -> Iterator[Issue]:
        href = ref.targets[0]
        if "#" not in href:
            yield Issue(
                severity=Severity.ERROR,
                rule="refs.MALFORMED_HREF",
                file_path=ref.file_path,
                line=ref.line,
                element_id=ref.source_element_id,
                element_name=ref.source_element_name,
                message=f"href '{href}' has no '#' separator",
            )
            return

        result = resolver.resolve_href(href, ref.file_path)
        if result.malformed:
            yield Issue(
                severity=Severity.ERROR,
                rule="refs.MALFORMED_HREF",
                file_path=ref.file_path,
                line=ref.line,
                element_id=ref.source_element_id,
                element_name=ref.source_element_name,
                message=f"Malformed href: '{href}'",
            )
        elif result.missing_file is not None:
            yield Issue(
                severity=Severity.ERROR,
                rule="refs.BROKEN_HREF_FILE",
                file_path=ref.file_path,
                line=ref.line,
                element_id=ref.source_element_id,
                element_name=ref.source_element_name,
                message=f"href '{href}' — file not found: {result.missing_file}",
            )
        elif result.missing_id is not None:
            yield Issue(
                severity=Severity.ERROR,
                rule="refs.BROKEN_HREF_ID",
                file_path=ref.file_path,
                line=ref.line,
                element_id=ref.source_element_id,
                element_name=ref.source_element_name,
                message=f"href '{href}' — id '{result.missing_id}' not found in target file",
            )

    def _check_idref(self, ref, resolver) -> Iterator[Issue]:
        for token in ref.targets:
            elem = resolver.resolve_idref(token)
            if elem is None:
                yield Issue(
                    severity=Severity.ERROR,
                    rule="refs.DANGLING_IDREF",
                    file_path=ref.file_path,
                    line=ref.line,
                    element_id=ref.source_element_id,
                    element_name=ref.source_element_name,
                    message=(
                        f"Attribute '{ref.attr_name}' references unknown id '{token}'"
                    ),
                )
                continue

            # Type mismatch check for specific attributes
            expected = _TYPE_ATTR_EXPECTED.get(ref.attr_name)
            if expected and elem.xmi_type not in expected:
                yield Issue(
                    severity=Severity.WARN,
                    rule="refs.HREF_TYPE_MISMATCH",
                    file_path=ref.file_path,
                    line=ref.line,
                    element_id=ref.source_element_id,
                    element_name=ref.source_element_name,
                    message=(
                        f"Attribute '{ref.attr_name}' points to '{elem.xmi_type}' "
                        f"('{elem.name}'), expected one of: {sorted(expected)}"
                    ),
                )
