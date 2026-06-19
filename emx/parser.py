"""Parse a single .emx (Eclipse XMI/UML2) file into an in-memory EmxFile."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lxml import etree

XMI_NS = "http://www.omg.org/XMI"
UML_NS_PREFIX = "http://www.eclipse.org/uml2/"

XMI_ID = f"{{{XMI_NS}}}id"
XMI_TYPE = f"{{{XMI_NS}}}type"

# Attributes whose values are space-separated IDREF lists
IDREF_ATTRS = {
    "general", "contract", "type", "memberEnd",
    "supplier", "client", "realizingClassifier",
    "navigableOwnedEnd", "redefinedElement", "redefinedConnector",
    "role", "partWithPort", "specific",
}

# Attributes that should hold exactly one IDREF (not a list)
SINGLE_IDREF_ATTRS = {"general", "contract", "type"}

_ID_LIKE = re.compile(r"^_[A-Za-z0-9_\-]+$")


@dataclass
class Element:
    xmi_id: str
    xmi_type: str          # e.g. "uml:Class"
    tag: str               # local tag name, e.g. "packagedElement"
    name: str              # value of 'name' attr, or ""
    attrs: dict            # all raw attributes
    file_path: Path
    line: int
    lower: Optional[str] = None  # value of the child <lowerValue>, if present
    upper: Optional[str] = None  # value of the child <upperValue>, if present


@dataclass
class RefSite:
    """One place in a file where a reference appears."""
    source_element_id: str
    source_element_name: str
    attr_name: str
    targets: list[str]     # individual ID tokens (or href strings)
    is_href: bool
    file_path: Path
    line: int


@dataclass
class EmxFile:
    path: Path
    elements: dict[str, Element] = field(default_factory=dict)  # xmi_id → Element
    refs: list[RefSite] = field(default_factory=list)
    duplicate_ids: list[tuple[str, int, int]] = field(default_factory=list)  # (id, line1, line2)
    # Elements that carry no xmi:id: (xmi_type, name, line)
    missing_ids: list[tuple[str, str, int]] = field(default_factory=list)


def _local_name(tag: str) -> str:
    """Strip namespace URI from a Clark-notation tag."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _qname_to_prefixed(tag: str, nsmap: dict) -> str:
    """Convert {uri}local to prefix:local using the element's nsmap."""
    if not tag.startswith("{"):
        return tag
    uri, local = tag[1:].split("}", 1)
    for prefix, ns_uri in nsmap.items():
        if ns_uri == uri and prefix:
            return f"{prefix}:{local}"
    return local


def _child_value(elem, child_local: str) -> Optional[str]:
    """Return the 'value' attribute of a direct child with the given local tag
    name (e.g. lowerValue/upperValue), or None if absent/empty."""
    for child in elem:
        if not isinstance(child.tag, str):
            continue
        if _local_name(child.tag) == child_local:
            val = child.get("value")
            return val if val else None
    return None


def parse_file(path: Path) -> EmxFile:
    emx = EmxFile(path=path)
    try:
        tree = etree.parse(str(path))
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"XML parse error in {path}: {exc}") from exc

    root = tree.getroot()
    id_lines: dict[str, int] = {}

    for elem in root.iter():
        if not isinstance(elem.tag, str):
            continue  # skip comments, PIs, etc.
        xmi_id: Optional[str] = elem.get(XMI_ID)
        xmi_type: Optional[str] = elem.get(XMI_TYPE) or _qname_to_prefixed(elem.tag, elem.nsmap)
        name: str = elem.get("name", "")
        tag: str = _local_name(elem.tag)
        line: int = elem.sourceline or 0
        attrs: dict = dict(elem.attrib)

        if xmi_id:
            if xmi_id in id_lines:
                emx.duplicate_ids.append((xmi_id, id_lines[xmi_id], line))
            else:
                id_lines[xmi_id] = line
                emx.elements[xmi_id] = Element(
                    xmi_id=xmi_id,
                    xmi_type=xmi_type or "",
                    tag=tag,
                    name=name,
                    attrs=attrs,
                    file_path=path,
                    line=line,
                    lower=_child_value(elem, "lowerValue"),
                    upper=_child_value(elem, "upperValue"),
                )
        else:
            emx.missing_ids.append((xmi_type or "", name, line))

        # Collect IDREF attributes
        for attr, val in attrs.items():
            # Skip namespace-qualified attributes (xmi:type, xmi:id, etc.) —
            # their values are type names / metadata, not IDREFs.
            if attr.startswith("{"):
                continue
            local_attr = _local_name(attr)
            val = val.strip()
            if not val:
                continue

            if local_attr == "href":
                ref_id = xmi_id or ""
                emx.refs.append(RefSite(
                    source_element_id=ref_id,
                    source_element_name=name,
                    attr_name="href",
                    targets=[val],
                    is_href=True,
                    file_path=path,
                    line=line,
                ))
            elif local_attr in IDREF_ATTRS:
                # Only keep tokens that look like xmi:id values (start with '_')
                tokens = [t for t in val.split() if t.startswith("_")]
                if tokens:
                    emx.refs.append(RefSite(
                        source_element_id=xmi_id or "",
                        source_element_name=name,
                        attr_name=local_attr,
                        targets=tokens,
                        is_href=False,
                        file_path=path,
                        line=line,
                    ))

    return emx
