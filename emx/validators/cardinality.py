"""Cardinality and multi-target reference validators."""

from __future__ import annotations

from typing import Iterator

from .base import BaseValidator, Issue, Severity

# These attributes should hold exactly one ID token
_SINGLE_VALUE_ATTRS = {"general", "contract", "type"}

_UNLIMITED = {"-1", "*"}


class CardinalityValidator(BaseValidator):
    def validate(self, registry, resolver) -> Iterator[Issue]:
        yield from self._check_single_ref_multiple_targets(registry)
        yield from self._check_multiplicity_inconsistency(registry)
        yield from self._check_unbounded_navigable_role(registry)

    def _check_single_ref_multiple_targets(self, registry) -> Iterator[Issue]:
        for ref in registry.all_refs():
            if ref.is_href:
                continue
            if ref.attr_name in _SINGLE_VALUE_ATTRS and len(ref.targets) > 1:
                yield Issue(
                    severity=Severity.ERROR,
                    rule="cardinality.SINGLE_REF_HAS_MULTIPLE_TARGETS",
                    file_path=ref.file_path,
                    line=ref.line,
                    element_id=ref.source_element_id,
                    element_name=ref.source_element_name,
                    message=(
                        f"Attribute '{ref.attr_name}' has {len(ref.targets)} targets "
                        f"({' '.join(ref.targets)}) — expected exactly 1"
                    ),
                )

    def _check_multiplicity_inconsistency(self, registry) -> Iterator[Issue]:
        for elem in registry.all_elements():
            if elem.xmi_type not in ("uml:Property", "uml:Parameter"):
                continue

            lower = elem.lower
            upper = elem.upper

            if lower is None or upper is None:
                continue
            if upper in _UNLIMITED:
                continue
            try:
                lo = int(lower)
                hi = int(upper)
            except ValueError:
                continue

            if lo > hi:
                yield Issue(
                    severity=Severity.ERROR,
                    rule="cardinality.MULTIPLICITY_INCONSISTENCY",
                    file_path=elem.file_path,
                    line=elem.line,
                    element_id=elem.xmi_id,
                    element_name=elem.name,
                    message=(
                        f"Multiplicity lower={lo} > upper={hi} on "
                        f"{elem.xmi_type} '{elem.name}'"
                    ),
                )

    def _check_unbounded_navigable_role(self, registry) -> Iterator[Issue]:
        for elem in registry.all_elements():
            if elem.xmi_type != "uml:Property":
                continue
            is_navigable = elem.attrs.get("isNavigable", "").lower() == "true"
            if not is_navigable:
                continue
            upper = elem.upper
            if upper is None:
                yield Issue(
                    severity=Severity.WARN,
                    rule="cardinality.UNBOUNDED_REQUIRED_ROLE",
                    file_path=elem.file_path,
                    line=elem.line,
                    element_id=elem.xmi_id,
                    element_name=elem.name,
                    message=(
                        f"Navigable role '{elem.name}' has no upperValue set "
                        f"(implicitly unbounded — may be unintentional)"
                    ),
                )
