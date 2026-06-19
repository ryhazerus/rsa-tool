"""UML structural rule validators."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterator

from .base import BaseValidator, Issue, Severity


class StructureValidator(BaseValidator):
    def validate(self, registry, resolver) -> Iterator[Issue]:
        yield from self._check_generalizations(registry, resolver)
        yield from self._check_interface_realizations(registry, resolver)
        yield from self._check_associations(registry, resolver)
        yield from self._check_dependencies(registry, resolver)
        yield from self._check_operation_params(registry)

    # ------------------------------------------------------------------

    def _check_generalizations(self, registry, resolver) -> Iterator[Issue]:
        # Build parent map for cycle detection: child_id → parent_id
        parent_map: dict[str, str] = {}

        for elem in registry.all_elements():
            if elem.xmi_type != "uml:Generalization":
                continue

            general = elem.attrs.get("general", "").strip()
            if not general:
                yield Issue(
                    severity=Severity.ERROR,
                    rule="structure.GENERALIZATION_MISSING_GENERAL",
                    file_path=elem.file_path,
                    line=elem.line,
                    element_id=elem.xmi_id,
                    element_name=elem.name,
                    message="uml:Generalization has no 'general' attribute",
                )
                continue

            # The specific (child) is the owning Classifier — navigate via xmi:id
            # The generalization element is owned by the specific class
            parent_map[elem.xmi_id] = general.split()[0]

        yield from self._detect_generalization_cycles(parent_map, registry, resolver)

    def _detect_generalization_cycles(self, parent_map, registry, resolver) -> Iterator[Issue]:
        # parent_map: gen_id → general_id (the parent class id)
        # Build child class → parent class map via generalization elements
        class_parent: dict[str, str] = {}
        for gen_id, parent_id in parent_map.items():
            gen_elem = registry.lookup_id(gen_id)
            if gen_elem is None:
                continue
            # The owning class is the parent element in the XML tree — we find it
            # by looking for any element whose xmi:id matches something that owns this gen
            # Simpler: walk all elements, find Classifiers whose 'generalization' attr includes gen_id
            pass

        # Alternative approach: find cycles by traversing the general attribute chain directly
        # We build: classifier_id → set of general_ids it directly points to
        generalizes: dict[str, set[str]] = defaultdict(set)
        for elem in registry.all_elements():
            if elem.xmi_type != "uml:Generalization":
                continue
            general = elem.attrs.get("general", "").strip()
            if not general:
                continue
            # Find owning classifier: it's the element with a 'generalization' attr containing this elem's id
            # We'll approximate by checking who has generalization= containing this id
            specific_id = elem.attrs.get("specific", "").strip()
            if specific_id:
                generalizes[specific_id].add(general.split()[0])

        # Now detect cycles via DFS
        visited: set[str] = set()
        in_stack: set[str] = set()
        reported: set[str] = set()

        def dfs(node: str, path: list[str]):
            if node in in_stack:
                cycle_start = path.index(node)
                cycle = path[cycle_start:]
                cycle_key = frozenset(cycle)
                if cycle_key not in reported:
                    reported.add(cycle_key)
                    elem = registry.lookup_id(node)
                    if elem:
                        yield Issue(
                            severity=Severity.ERROR,
                            rule="structure.CIRCULAR_GENERALIZATION",
                            file_path=elem.file_path,
                            line=elem.line,
                            element_id=node,
                            element_name=elem.name,
                            message=f"Circular generalization: {' → '.join(cycle + [node])}",
                        )
                return
            if node in visited:
                return
            visited.add(node)
            in_stack.add(node)
            path.append(node)
            for parent in generalizes.get(node, set()):
                yield from dfs(parent, path)
            path.pop()
            in_stack.discard(node)

        for node in list(generalizes.keys()):
            yield from dfs(node, [])

    def _check_interface_realizations(self, registry, resolver) -> Iterator[Issue]:
        # Track (owner_id, contract_id) pairs to detect duplicates
        seen: dict[str, set[str]] = defaultdict(set)

        for elem in registry.all_elements():
            if elem.xmi_type != "uml:InterfaceRealization":
                continue

            contract = elem.attrs.get("contract", "").strip()
            if not contract:
                yield Issue(
                    severity=Severity.ERROR,
                    rule="structure.INTERFACE_REALIZATION_MISSING_CONTRACT",
                    file_path=elem.file_path,
                    line=elem.line,
                    element_id=elem.xmi_id,
                    element_name=elem.name,
                    message="uml:InterfaceRealization has no 'contract' attribute",
                )
                continue

            client = elem.attrs.get("client", "").strip()
            owner_id = client.split()[0] if client else elem.xmi_id

            contract_id = contract.split()[0]
            if contract_id in seen[owner_id]:
                owner_elem = registry.lookup_id(owner_id)
                owner_name = owner_elem.name if owner_elem else owner_id
                contract_elem = registry.lookup_id(contract_id)
                contract_name = contract_elem.name if contract_elem else contract_id
                yield Issue(
                    severity=Severity.ERROR,
                    rule="structure.DUPLICATE_INTERFACE_REALIZATION",
                    file_path=elem.file_path,
                    line=elem.line,
                    element_id=elem.xmi_id,
                    element_name=elem.name,
                    message=(
                        f"'{owner_name}' realizes interface '{contract_name}' more than once"
                    ),
                )
            else:
                seen[owner_id].add(contract_id)

    def _check_associations(self, registry, resolver) -> Iterator[Issue]:
        for elem in registry.all_elements():
            if elem.xmi_type != "uml:Association":
                continue

            member_end = elem.attrs.get("memberEnd", "").strip()
            if not member_end:
                yield Issue(
                    severity=Severity.ERROR,
                    rule="structure.ASSOCIATION_WRONG_END_COUNT",
                    file_path=elem.file_path,
                    line=elem.line,
                    element_id=elem.xmi_id,
                    element_name=elem.name,
                    message="uml:Association has no 'memberEnd' attribute (expected 2 ends)",
                )
                continue

            tokens = member_end.split()
            if len(tokens) != 2:
                yield Issue(
                    severity=Severity.ERROR,
                    rule="structure.ASSOCIATION_WRONG_END_COUNT",
                    file_path=elem.file_path,
                    line=elem.line,
                    element_id=elem.xmi_id,
                    element_name=elem.name,
                    message=(
                        f"uml:Association '{elem.name}' has {len(tokens)} memberEnd token(s), "
                        f"expected exactly 2"
                    ),
                )

            for token in tokens:
                end_elem = resolver.resolve_idref(token)
                if end_elem is None:
                    yield Issue(
                        severity=Severity.ERROR,
                        rule="structure.ASSOCIATION_END_NOT_FOUND",
                        file_path=elem.file_path,
                        line=elem.line,
                        element_id=elem.xmi_id,
                        element_name=elem.name,
                        message=f"memberEnd '{token}' does not resolve to any known element",
                    )

    def _check_dependencies(self, registry, resolver) -> Iterator[Issue]:
        dep_types = {"uml:Dependency", "uml:Usage", "uml:Realization"}
        for elem in registry.all_elements():
            if elem.xmi_type not in dep_types:
                continue

            supplier = elem.attrs.get("supplier", "").strip()
            client = elem.attrs.get("client", "").strip()

            if not supplier:
                yield Issue(
                    severity=Severity.ERROR,
                    rule="structure.DEPENDENCY_MISSING_SUPPLIER",
                    file_path=elem.file_path,
                    line=elem.line,
                    element_id=elem.xmi_id,
                    element_name=elem.name,
                    message=f"{elem.xmi_type} '{elem.name}' has no 'supplier'",
                )
            if not client:
                yield Issue(
                    severity=Severity.ERROR,
                    rule="structure.DEPENDENCY_MISSING_CLIENT",
                    file_path=elem.file_path,
                    line=elem.line,
                    element_id=elem.xmi_id,
                    element_name=elem.name,
                    message=f"{elem.xmi_type} '{elem.name}' has no 'client'",
                )

    def _check_operation_params(self, registry) -> Iterator[Issue]:
        for elem in registry.all_elements():
            if elem.xmi_type != "uml:Parameter":
                continue
            direction = elem.attrs.get("direction", "").strip()
            type_val = elem.attrs.get("type", "").strip()
            # return parameters without a type are fine (void return)
            if direction == "return":
                continue
            if not type_val:
                yield Issue(
                    severity=Severity.WARN,
                    rule="structure.OPERATION_PARAM_TYPE_MISSING",
                    file_path=elem.file_path,
                    line=elem.line,
                    element_id=elem.xmi_id,
                    element_name=elem.name,
                    message=(
                        f"Parameter '{elem.name}' has no 'type' attribute"
                    ),
                )
