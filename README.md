# EMX Tools

Two standalone CLI tools for working with `.emx` UML model files (the XML format used by IBM RSA and compatible UML tooling).

**No RSA installation required.** `.emx` files are plain XML — these tools only need Python and `lxml` to run.

- **`main.py`** — validates `.emx` files for structural, reference, and cardinality errors
- **`rewire.py`** — edits `uml:Connector` ends by part/port name without touching XML IDs by hand

---

## Requirements

- Python 3.9+
- `lxml` (`pip install lxml`)

```bash
pip install -r requirements.txt
```

---

## Validator (`main.py`)

Scans one or more `.emx` files (or directories) and reports issues across four rule groups:

| Group | Example rules |
|---|---|
| `ids` | duplicate `xmi:id` within or across files |
| `refs` | broken `href` links, dangling ID references |
| `structure` | circular generalization, missing `contract`, wrong association end count |
| `cardinality` | `lower > upper` multiplicity, single-target attribute with multiple IDs |

### Basic usage

```bash
# Validate a single file
python main.py model.emx

# Validate an entire RSA project directory (recursive by default)
python main.py ./my-rsa-project

# Validate multiple files at once
python main.py interfaces.emx components.emx

# Non-recursive directory scan
python main.py ./my-rsa-project --no-recursive
```

### Options

```
--format text|json       Output format (default: text)
--severity info|warn|error  Minimum severity to show (default: info)
--rules RULE,...         Only report these rules (comma-separated)
--exclude-rules RULE,... Suppress these rules (comma-separated)
--exit-code              Exit with code 1 if any errors found (for CI)
```

### Examples

```bash
# Only show errors, not warnings or info
python main.py ./project --severity error

# JSON output (useful for piping into other tools)
python main.py ./project --format json

# CI gate — fails the build if there are errors
python main.py ./project --exit-code

# Suppress cross-file duplicate ID noise when validating fixtures in isolation
python main.py model.emx --exclude-rules ids.DUPLICATE_ID_CROSS_FILE

# Check only reference rules
python main.py ./project --rules refs.BROKEN_HREF_FILE,refs.DANGLING_IDREF
```

### Example output

Clean file:

```
Validated 1 file(s).

No issues found.
```

File with errors (text format):

```
Validated 1 file(s).

[ERROR]  refs.BROKEN_HREF_FILE                    broken_href.emx:11
         href 'nonexistent_interfaces.emx#_iface99' — file not found: /workspace/nonexistent_interfaces.emx
[ERROR]  refs.MALFORMED_HREF                      broken_href.emx:16
         href 'no_hash_here' has no '#' separator
[ERROR]  structure.INTERFACE_REALIZATION_MISSING_CONTRACT broken_href.emx:10
         element:  _ir01
         uml:InterfaceRealization has no 'contract' attribute
[ERROR]  cardinality.MULTIPLICITY_INCONSISTENCY   bad_cardinality.emx:21
         element:  _prop01  readings
         Multiplicity lower=3 > upper=1 on uml:Property 'readings'
[ERROR]  structure.CIRCULAR_GENERALIZATION        circular_generalization.emx:9
         element:  _clsA  ClassA
         Circular generalization: _clsA → _clsB → _clsC → _clsA

5 error(s) found.
```

Same errors as JSON (`--format json`):

```json
[
  {
    "severity": "ERROR",
    "rule": "refs.BROKEN_HREF_FILE",
    "file": "broken_href.emx",
    "line": 11,
    "element_id": "_ir01",
    "element_name": "",
    "message": "href 'nonexistent_interfaces.emx#_iface99' — file not found: ..."
  }
]
```

---

## Rewire tool (`rewire.py`)

Edits `uml:Connector` ends in an `.emx` file by looking up parts/ports by name. Automatically backs up the original file before modifying it in place.

### Connector end kinds

| Kind | When | `--end0/--end1` updates |
|---|---|---|
| `[direct]` | `role == partWithPort` (or no `partWithPort`) | both `role` and `partWithPort` |
| `[port]` | `role != partWithPort` | `role` only — use `--pwp0/--pwp1` for the owning part |

### Basic usage

```bash
# Show current connector ends (no changes made)
python rewire.py model.emx --connector "link1" --show

# Rewire both ends (direct part-to-part)
python rewire.py model.emx --connector "link1" --end0 "SensorA" --end1 "ActuatorB"

# Rewire only one end
python rewire.py model.emx --connector "link1" --end0 "SensorA"

# Swap both ends
python rewire.py model.emx --connector "link1" --swap

# Write to a new file instead of modifying in place
python rewire.py model.emx --connector "link1" --end0 "SensorA" --out updated.emx
```

### Port-based connections

When an end is `[port]`-kind (the connector goes through a port), `--end0/--end1` updates only the port role. Use `--pwp0/--pwp1` to also change the owning part:

```bash
# Change the port only
python rewire.py model.emx --connector "link1" --end0 "outPort"

# Change the port AND its owning part
python rewire.py model.emx --connector "link1" --end0 "outPort" --pwp0 "NewPart"
```

### Options

```
--connector/-c NAME   Name of the uml:Connector to target (required)
--show                Print current end configuration and exit
--end0 NAME           Part or port name for end[0]
--end1 NAME           Part or port name for end[1]
--pwp0 NAME           Owning part for end[0] (port-based ends)
--pwp1 NAME           Owning part for end[1] (port-based ends)
--swap                Swap both ends (cannot combine with --end0/--end1)
--out FILE            Write output here instead of modifying in place
```

### Example output

Inspecting a connector (`--show`):

```
Connector: 'link1'  (2 end(s))
  end[0]  [direct]  part='sensorPart'  (id=_partSensor)
  end[1]  [direct]  part='actuatorPart'  (id=_partActuator)
```

Rewiring both ends to a new file (`--out`):

```
  end[0] role: 'sensorPart' → 'actuatorPart'
  end[1] role: 'actuatorPart' → 'sensorPart'
Written to: rewired.emx
```

Swapping in place (`--swap`), which also creates a backup:

```
  Swapped ends of connector 'link1'.
Backup created: model.emx.bak_original
Written to: model.emx
```

Error — connector not found:

```
ERROR: No uml:Connector named 'badname' found in model.emx.
```

Error — part name not found:

```
ERROR: No uml:Property or uml:Port named 'NOSUCHPART' found in the file.
```

---

## Running with Podman

The container mounts your RSA project directory at `/workspace`. Both tools are available inside as `python /app/main.py` and `python /app/rewire.py`.

### Build the image

```bash
podman build -t rsa-emx-tools .
```

### Validate a project

```bash
# Validate everything under /path/to/your/rsa-project
podman run --rm \
  -v /path/to/your/rsa-project:/workspace:ro,z \
  rsa-emx-tools \
  python /app/main.py .

# JSON output piped to a local file
podman run --rm \
  -v /path/to/your/rsa-project:/workspace:ro,z \
  rsa-emx-tools \
  python /app/main.py . --format json > report.json

# CI gate
podman run --rm \
  -v /path/to/your/rsa-project:/workspace:ro,z \
  rsa-emx-tools \
  python /app/main.py . --severity error --exit-code
```

### Rewire a connector

Because rewire modifies files, mount the directory read-write and use `--out` to write to a safe output path:

```bash
# Show connector ends (read-only mount is fine)
podman run --rm \
  -v /path/to/your/rsa-project:/workspace:ro,z \
  rsa-emx-tools \
  python /app/rewire.py model.emx --connector "link1" --show

# Rewire and write output to /workspace (read-write mount required)
podman run --rm \
  -v /path/to/your/rsa-project:/workspace:z \
  rsa-emx-tools \
  python /app/rewire.py model.emx --connector "link1" --end0 "SensorA" --out rewired.emx
```

> The rewire tool creates a backup (`.bak_original`) next to the output file when writing in place. When using `--out`, no backup is created since the original is untouched.

### Validating a single file

```bash
podman run --rm \
  -v /path/to/your/rsa-project:/workspace:ro,z \
  rsa-emx-tools \
  python /app/main.py interfaces.emx
```

Paths passed to the tools are relative to `/workspace` (the mount point).

> **Note on `:z`** — the `z` option relabels the volume for SELinux, which is required on Fedora/RHEL hosts. On non-SELinux systems (Debian, Ubuntu, macOS) you can omit it and use `:ro` alone.
