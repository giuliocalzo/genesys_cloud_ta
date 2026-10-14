# CIM 5.x Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Map Genesys Cloud audit events to the CIM Change data model and edge
metrics to the CIM Performance data model, verified by pytest-splunk-addon.

**Architecture:** Search-time knowledge (`props.conf`, `eventtypes.conf`,
`tags.conf`) in `package/default/`, plus one additive ingestion change: the
edges metrics input writes the per-event disk sums that `eval` cannot compute.

**Tech Stack:** Splunk props/eventtypes/tags, UCC (`ucc-gen`), pytest,
pytest-splunk-addon 6.4.0, Docker `splunk/splunk:10.2.0`, GitHub Actions.

Spec: `docs/superpowers/specs/2026-10-14-cim-5x-compatibility-design.md`

## Global Constraints

- pytest-splunk-addon is pinned to `6.4.0` (7.x and 8.x need the private
  `splunk_cim_models` package).
- `.splunkbase`: `SPLUNKBASE_SPLUNK_CIM_VERSION=5.0,5.1,5.2,5.3`.
- Audit mappings read both key shapes, e.g. `coalesce(entity_type, entityType)`.
- No existing event field is renamed or removed.
- No version bump; CHANGELOG gets an `Unreleased` section.
- Every commit uses `git commit -s`; commit subjects follow the repo's
  `type:summary` style (e.g. `feat:...`, `test:...`, `docs:...`).

---

### Task 1: Disk sums on edge metrics events

**Files:**
- Modify: `package/bin/genesyscloud_models.py` (`EdgeModel`)
- Modify: `package/bin/edges_metrics_helper.py` (event loop)
- Create: `tests/unit/__init__.py`, `tests/unit/test_genesyscloud_models.py`
- Modify: `tests/pytest.ini` (`testpaths`), `.github/workflows/tests.yml`
  (run `unit/` before the container tests)

**Interfaces:**
- Produces: `EdgeModel.sum_disks(disks: Optional[List[dict]]) -> Tuple[float, float]`
  returning `(total_bytes, available_bytes)`; event keys `disks_total_bytes`
  and `disks_available_bytes` (consumed by Task 2).

- [ ] **Step 1: Write the failing test** in `tests/unit/test_genesyscloud_models.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "package", "bin"))

from genesyscloud_models import EdgeModel


def test_sum_disks_adds_every_disk():
    disks = [
        {"partition_name": "/dev/a", "total_bytes": 100.0, "available_bytes": 40.0},
        {"partition_name": "/dev/b", "total_bytes": 50.0, "available_bytes": 10.0},
    ]
    assert EdgeModel.sum_disks(disks) == (150.0, 50.0)


def test_sum_disks_treats_null_values_as_zero():
    disks = [{"partition_name": "/dev/a", "total_bytes": None, "available_bytes": 5.0}]
    assert EdgeModel.sum_disks(disks) == (0, 5.0)


def test_sum_disks_empty_list():
    assert EdgeModel.sum_disks([]) == (0, 0)


def test_sum_disks_missing():
    assert EdgeModel.sum_disks(None) == (0, 0)
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd tests && python -m pytest unit -v`
Expected: FAIL, `AttributeError: type object 'EdgeModel' has no attribute 'sum_disks'`

- [ ] **Step 3: Implement** on `EdgeModel`:

```python
    @staticmethod
    def sum_disks(disks: Optional[List[dict]]) -> Tuple[float, float]:
        disks = disks or []
        total = sum(disk.get("total_bytes") or 0 for disk in disks)
        available = sum(disk.get("available_bytes") or 0 for disk in disks)
        return total, available
```

and in `edges_metrics_helper.py`, after `metric = metric_obj.to_dict()`:

```python
                metric["disks_total_bytes"], metric["disks_available_bytes"] = e_model.sum_disks(metric.get("disks"))
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `cd tests && python -m pytest unit -v`
Expected: 4 passed

- [ ] **Step 5: Wire into CI.** Add `unit` to `testpaths` in `tests/pytest.ini`
  and a `Run unit tests` step (`python -m pytest unit/ --junitxml=junit/unit-test-results-${{ matrix.version }}.xml`)
  after `pip install -r test-requirements.txt` in both jobs of
  `.github/workflows/tests.yml`. Add `.github/workflows/tests.yml` to its own
  `paths` filter so workflow edits run it.

- [ ] **Step 6: Commit** — `feat:added disk sums to edges metrics events`

### Task 2: Change and Performance mappings, verified by pytest-splunk-addon

**Files:**
- Modify: `package/default/props.conf`
- Create: `package/default/eventtypes.conf`, `package/default/tags.conf`
- Create: `tests/knowledge/pytest.ini`,
  `tests/knowledge/requirements.txt`, `tests/knowledge/test_addon.py`,
  `tests/knowledge/pytest-splunk-addon-data.conf`,
  `tests/knowledge/samples/genesyscloud_audits.xml`,
  `tests/knowledge/samples/genesyscloud_edges_metrics.xml`
- Create: `.github/workflows/cim.yml`

**Interfaces:**
- Consumes: `disks_total_bytes`, `disks_available_bytes` from Task 1.
- Produces: event types `genesyscloud_audit_change`,
  `genesyscloud_audit_account`, `genesyscloud_edge_performance`,
  `genesyscloud_edge_storage` (documented in Task 4).

- [ ] **Step 1: Write the samples first** (they are the failing test). XML
  samples with `requirement_test_sample = 1`, one `<event>` per case, each
  `<cim_fields>` listing the expected CIM values:
  - audit, snake_case, `Update` on a `Queue` → `action=updated`, `status=success`
  - audit, camelCase (download shape), `Delete` on a `Queue`, `FAILURE` →
    `action=deleted`, `status=failure`, `result=<message>`
  - audit, snake_case, `Create` on a `User` → `tag=account`, `user=<entity>`,
    `src_user=<actor>`, `object_category=user`
  - edge metrics with three processors (`cpu0`, `cpu1`, `total`), `physical`
    and `virtual` memory, two disks plus the disk sums.

- [ ] **Step 2: Build and run PSA against an unconfigured add-on; confirm it fails**

```bash
ucc-gen build --ta-version "$(jq -r '.info.id.version' package/app.manifest)"
docker run -d --name splunk-cim -p 8089:8089 -p 8088:8088 \
  -e SPLUNK_START_ARGS="--accept-license" -e SPLUNK_GENERAL_TERMS="--accept-sgt-current-at-splunk-com" \
  -e SPLUNK_PASSWORD=Chang3d! -e SPLUNK_HEC_TOKEN=00000000-0000-0000-0000-000000000000 \
  -v "$PWD/output/genesys_cloud_ta:/opt/splunk/etc/apps/genesys_cloud_ta" splunk/splunk:10.2.0
cd tests/knowledge && python -m pytest
```

Expected: CIM tests fail (no tags, no CIM fields).

- [ ] **Step 3: Write `props.conf`, `eventtypes.conf`, `tags.conf`** exactly as
  specified in the spec's mapping tables.

- [ ] **Step 4: Rebuild, restart Splunk, re-run PSA; iterate until green**

Run: `cd tests/knowledge && python -m pytest`
Expected: all generated `splunk_searchtime_fields`, `splunk_searchtime_cim`
and `splunk_requirements` tests pass.

- [ ] **Step 5: Add `.github/workflows/cim.yml`** running the same build,
  container and pytest command on pull requests touching `package/**` or
  `tests/knowledge/**`; upload the junit report.

- [ ] **Step 6: Commit** — `feat:added CIM 5.x Change and Performance mappings`

### Task 3: Declare CIM compatibility

**Files:** `.splunkbase`

- [ ] **Step 1:** Set `SPLUNKBASE_SPLUNK_CIM_VERSION=5.0,5.1,5.2,5.3`. Leave
  `app.manifest` alone: SLIM 1.2.8 only knows CIM models up to 4.5 and has no
  `Change`, so a `commonInformationModels` entry would fail validation.
- [ ] **Step 2: Verify** `source .splunkbase && echo "$SPLUNKBASE_SPLUNK_CIM_VERSION"`
  prints `5.0,5.1,5.2,5.3`.
- [ ] **Step 3: Commit** — `chore:declared CIM 5.x compatibility`

### Task 4: Documentation

**Files:** Create `docs/CIM/index.md`; modify `docs/Sourcetypes/index.md`,
`mkdocs.yml`, `CHANGELOG.md`

- [ ] **Step 1:** Write `docs/CIM/index.md` (mapped sourcetypes, event types,
  field tables, Storage caveat, manual `| datamodel` validation searches),
  add a "CIM data model" column to the Sourcetypes table, add the nav entry,
  add an `Unreleased` CHANGELOG section.
- [ ] **Step 2: Verify** `mkdocs build --strict` succeeds.
- [ ] **Step 3: Commit** — `docs:added CIM compatibility page`
