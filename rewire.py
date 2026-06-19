#!/usr/bin/env python3
"""
Rewire connector ends in an IBM RSA .emx file.

A uml:Connector has two ends (uml:ConnectorEnd).  Each end has:
  role          — the part (or port) being connected
  partWithPort  — (optional) the part that owns the port; only set when
                  the connection goes through a port

Two end kinds are detected automatically:

  [direct]  role == partWithPort (or partWithPort absent)
            → changing --end0/--end1 updates both role and partWithPort.

  [port]    role != partWithPort
            → role is a port, partWithPort is its owning part.
              Changing --end0/--end1 updates ONLY role.
              Use --pwp0/--pwp1 to also change the owning part.

Usage examples
--------------
  # Show current ends (no changes)
  python rewire.py model.emx --connector "link1" --show

  # Direct part-to-part rewire
  python rewire.py model.emx --connector "link1" --end0 "SensorA" --end1 "ActuatorB"

  # Port-based: change port on end[0], leave owning part alone
  python rewire.py model.emx --connector "link1" --end0 "outPort"

  # Port-based: change port AND owning part on end[0]
  python rewire.py model.emx --connector "link1" --end0 "outPort" --pwp0 "NewPart"

  # Swap both ends
  python rewire.py model.emx --connector "link1" --swap

  # Write to a new file instead of modifying in place
  python rewire.py model.emx --connector "link1" --end0 "A" --out updated.emx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lxml import etree

XMI_NS = "http://www.omg.org/XMI"

XMI_ID   = f"{{{XMI_NS}}}id"
XMI_TYPE = f"{{{XMI_NS}}}type"

WARN = "\033[33mWARN\033[0m"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if tag.startswith("{") else tag


def _xmi_type(elem) -> str:
    return elem.get(XMI_TYPE) or _local(elem.tag)


def _load(path: Path) -> etree._ElementTree:
    try:
        parser = etree.XMLParser(remove_comments=False, remove_pis=False)
        return etree.parse(str(path), parser)
    except etree.XMLSyntaxError as exc:
        _die(f"XML parse error in {path}: {exc}")


def _die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _warn(msg: str) -> None:
    print(f"{WARN}  {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# End-kind detection
# ---------------------------------------------------------------------------

def _end_kind(end: etree._Element) -> str:
    """
    'direct' — role == partWithPort (or partWithPort absent): plain part connection.
    'port'   — role != partWithPort: role is a port, partWithPort is the owning part.
    """
    role = end.get("role", "")
    pwp  = end.get("partWithPort", "")
    if pwp and pwp != role:
        return "port"
    return "direct"


# ---------------------------------------------------------------------------
# Model queries
# ---------------------------------------------------------------------------

def find_connector(root: etree._Element, name: str) -> etree._Element | None:
    for elem in root.iter():
        if not isinstance(elem.tag, str):
            continue
        if _xmi_type(elem) == "uml:Connector" and elem.get("name") == name:
            return elem
    return None


def connector_ends(connector: etree._Element) -> list[etree._Element]:
    ends = []
    for child in connector:
        if not isinstance(child.tag, str):
            continue
        if _xmi_type(child) == "uml:ConnectorEnd" or _local(child.tag) == "end":
            ends.append(child)
    return ends


def find_element_by_name(root: etree._Element, name: str,
                         kinds: tuple[str, ...] = ("uml:Property",)
                         ) -> etree._Element | None:
    for elem in root.iter():
        if not isinstance(elem.tag, str):
            continue
        if _xmi_type(elem) in kinds and elem.get("name") == name:
            return elem
    return None


def _resolve_name(xmi_id: str, root: etree._Element) -> str:
    if not xmi_id:
        return "(none)"
    for elem in root.iter():
        if not isinstance(elem.tag, str):
            continue
        if elem.get(XMI_ID) == xmi_id:
            return elem.get("name") or xmi_id
    return xmi_id


def _describe_end(end: etree._Element, root: etree._Element, idx: int) -> None:
    kind     = _end_kind(end)
    role_id  = end.get("role", "")
    pwp_id   = end.get("partWithPort", "")

    role_name = _resolve_name(role_id, root)
    pwp_name  = _resolve_name(pwp_id,  root) if pwp_id else None

    if kind == "direct":
        print(f"  end[{idx}]  [direct]  part='{role_name}'  (id={role_id or '—'})")
    else:
        print(f"  end[{idx}]  [port]    port='{role_name}'  (id={role_id or '—'})")
        print(f"             on part='{pwp_name}'  (id={pwp_id or '—'})")


# ---------------------------------------------------------------------------
# Low-level attribute setter
# ---------------------------------------------------------------------------

def _set_attr(elem: etree._Element, attr: str, value: str | None) -> None:
    """Set or remove an attribute."""
    if value:
        elem.set(attr, value)
    elif value is not None and attr in elem.attrib:
        del elem.attrib[attr]


# ---------------------------------------------------------------------------
# Rewire logic
# ---------------------------------------------------------------------------

def _rewire_end(
    end: etree._Element,
    root: etree._Element,
    label: str,
    new_role_name: str | None,
    new_pwp_name: str | None,
) -> bool:
    """
    Rewire one connector end.  Returns True if anything changed.
    Emits warnings when port-based topology is detected.
    """
    kind     = _end_kind(end)
    changed  = False

    if new_role_name is not None:
        part = find_element_by_name(root, new_role_name,
                                    kinds=("uml:Property", "uml:Port"))
        if part is None:
            _die(f"No uml:Property or uml:Port named '{new_role_name}' found in the file.")
        new_role_id = part.get(XMI_ID, "")
        if not new_role_id:
            _die(f"Element '{new_role_name}' has no xmi:id.")

        old_role_name = _resolve_name(end.get("role", ""), root)

        if kind == "direct":
            # Simple case: role and partWithPort move together
            _set_attr(end, "role", new_role_id)
            if end.get("partWithPort"):
                _set_attr(end, "partWithPort", new_role_id)
            print(f"  {label} role: '{old_role_name}' → '{new_role_name}'")
        else:
            # Port case: only update role (the port); leave partWithPort untouched
            _warn(
                f"{label} is port-based "
                f"(role='{old_role_name}' is a port on "
                f"part='{_resolve_name(end.get('partWithPort',''), root)}'). "
                f"Updating role only. Use --pwp{label[-2]} to also change the owning part."
            )
            _set_attr(end, "role", new_role_id)
            print(f"  {label} role: '{old_role_name}' → '{new_role_name}'  [port only]")

        changed = True

    if new_pwp_name is not None:
        part = find_element_by_name(root, new_pwp_name,
                                    kinds=("uml:Property", "uml:Port"))
        if part is None:
            _die(f"No uml:Property named '{new_pwp_name}' found in the file.")
        new_pwp_id = part.get(XMI_ID, "")
        if not new_pwp_id:
            _die(f"Element '{new_pwp_name}' has no xmi:id.")

        if kind == "direct" and new_role_name is None:
            _warn(
                f"{label} is a direct (non-port) end. Setting partWithPort separately "
                "will make role != partWithPort, turning this into a port-based end."
            )

        old_pwp_name = _resolve_name(end.get("partWithPort", ""), root)
        _set_attr(end, "partWithPort", new_pwp_id)
        print(f"  {label} partWithPort: '{old_pwp_name}' → '{new_pwp_name}'")
        changed = True

    return changed


def rewire(
    root: etree._Element,
    connector_name: str,
    end0_role: str | None,
    end1_role: str | None,
    end0_pwp: str | None,
    end1_pwp: str | None,
    swap: bool,
) -> bool:
    connector = find_connector(root, connector_name)
    if connector is None:
        _die(f"No uml:Connector named '{connector_name}' found in the file.")

    ends = connector_ends(connector)
    if len(ends) < 2:
        _die(
            f"Connector '{connector_name}' has {len(ends)} end(s); expected at least 2."
        )

    if swap:
        role0 = ends[0].get("role", "")
        role1 = ends[1].get("role", "")
        pwp0  = ends[0].get("partWithPort", "")
        pwp1  = ends[1].get("partWithPort", "")
        kind0 = _end_kind(ends[0])
        kind1 = _end_kind(ends[1])

        if kind0 != kind1:
            _warn(
                f"end[0] is [{kind0}] and end[1] is [{kind1}] — swapping mixed-kind ends. "
                "Verify the result carefully."
            )

        _set_attr(ends[0], "role", role1)
        _set_attr(ends[0], "partWithPort", pwp1 or None)
        _set_attr(ends[1], "role", role0)
        _set_attr(ends[1], "partWithPort", pwp0 or None)
        print(f"  Swapped ends of connector '{connector_name}'.")
        return True

    changed  = False
    changed |= _rewire_end(ends[0], root, "end[0]", end0_role, end0_pwp)
    changed |= _rewire_end(ends[1], root, "end[1]", end1_role, end1_pwp)
    return changed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Rewire uml:Connector ends in an IBM RSA .emx file by part/port name.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("emx_file", metavar="FILE", help=".emx file to modify")
    ap.add_argument("--connector", "-c", required=True, metavar="NAME",
                    help="Name of the uml:Connector to rewire")
    ap.add_argument("--show", action="store_true",
                    help="Print current end configuration and exit (no changes)")
    ap.add_argument("--end0", metavar="NAME",
                    help="Part or port name to set as role on end[0]")
    ap.add_argument("--end1", metavar="NAME",
                    help="Part or port name to set as role on end[1]")
    ap.add_argument("--pwp0", metavar="NAME",
                    help="Part name to set as partWithPort on end[0] (port-based ends)")
    ap.add_argument("--pwp1", metavar="NAME",
                    help="Part name to set as partWithPort on end[1] (port-based ends)")
    ap.add_argument("--swap", action="store_true",
                    help="Swap both ends (role and partWithPort)")
    ap.add_argument("--out", metavar="FILE",
                    help="Write result here instead of modifying in place")

    args = ap.parse_args(argv)

    if args.swap and (args.end0 or args.end1 or args.pwp0 or args.pwp1):
        ap.error("--swap cannot be combined with --end0/--end1/--pwp0/--pwp1")

    path = Path(args.emx_file)
    if not path.exists():
        _die(f"File not found: {path}")

    tree = _load(path)
    root = tree.getroot()

    connector = find_connector(root, args.connector)
    if connector is None:
        _die(f"No uml:Connector named '{args.connector}' found in {path}.")

    ends = connector_ends(connector)

    if args.show or not any([args.end0, args.end1, args.pwp0, args.pwp1, args.swap]):
        print(f"Connector: '{args.connector}'  ({len(ends)} end(s))")
        for i, end in enumerate(ends):
            _describe_end(end, root, i)
        return 0

    changed = rewire(
        root, args.connector,
        args.end0, args.end1,
        args.pwp0, args.pwp1,
        args.swap,
    )

    if changed:
        out_path = Path(args.out) if args.out else path

        # Back up the source file only when we are about to overwrite it
        if out_path.resolve() == path.resolve():
            bak = Path.cwd() / (path.name + ".bak_original")
            if bak.exists():
                print(f"Backup already exists, keeping original: {bak}")
            else:
                bak.write_bytes(path.read_bytes())
                print(f"Backup created: {bak}")

        xml_bytes = etree.tostring(
            tree,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )
        out_path.write_bytes(xml_bytes)
        print(f"Written to: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
