# CIM 5.x compatibility

## Goal

Make the Genesys Cloud Add-on for Splunk compatible with the Splunk Common
Information Model (CIM) 5.x, so that audit events populate the **Change** data
model and edge metrics populate the **Performance** data model. Searches,
dashboards and Splunk Enterprise Security content built on these data models
then work with Genesys Cloud data without vendor-specific SPL.

Reference: <https://docs.splunk.com/Documentation/CIM/5.0.0>

## Scope

| Sourcetype | CIM data model | Datasets |
|---|---|---|
| `genesyscloud:operational:audits` | Change | `All_Changes`, `Account_Management` |
| `genesyscloud:telephonyprovidersedge:edges:metrics` | Performance | `CPU`, `Memory`, `Storage`, `Uptime` |

### Out of scope

- `genesyscloud:telephonyprovidersedge:edges:phones`,
  `genesyscloud:telephonyprovidersedge:trunks:metrics`,
  `genesyscloud:operational:system`, and every `genesyscloud:analytics:*` and
  `genesyscloud:users:*` sourcetype. No CIM 5.x data model fits contact-center
  KPIs (MOS, routing statuses, queue observations); they stay vendor-specific.
- The Authentication data model. There is no evidence that Genesys Cloud audit
  events carry login events.
- CIM 6.x certification. The Change and Performance models are unchanged in 6.x,
  but declaring and testing it is a separate decision.
- Splitting edge metrics into one event per CPU or disk.

## Design

All mappings are search-time knowledge in `package/default/`, so they apply
retroactively to data that is already indexed. The single exception is an
additive change to the edges metrics input (see Storage below).

Value normalization uses `case()` inside `EVAL-` statements. No lookup files.

### Files

| File | Change |
|---|---|
| `package/default/props.conf` | `KV_MODE = json`, `FIELDALIAS-` and `EVAL-` for both sourcetypes; keep the existing `TRUNCATE = 0` stanza |
| `package/default/eventtypes.conf` | New: three event types (below) |
| `package/default/tags.conf` | New: tags per event type (below) |
| `package/bin/genesyscloud_models.py` | `EdgeModel` gains a static method that sums a metric's `disks` into total and available bytes |
| `package/bin/edges_metrics_helper.py` | Calls that method and adds `disks_total_bytes` and `disks_available_bytes` to each event |
| `.splunkbase` | `SPLUNKBASE_SPLUNK_CIM_VERSION=5.0,5.1,5.2,5.3` |
| `docs/CIM/index.md` | New page: mapped fields per data model, validation searches |
| `docs/Sourcetypes/index.md` | New "CIM data model" column |
| `mkdocs.yml` | Nav entry for the new page |
| `CHANGELOG.md` | `Unreleased` entry; no version bump |

`ucc-gen publish --cim-versions` takes comma-separated `major.minor` values
(its help text uses `'4.9,6.1'` as the example), so `.splunkbase` lists each
5.x minor rather than `5.x`. Confirm during implementation that Splunkbase
accepts each listed minor.

`app.manifest` is left unchanged: the packaging toolkit (SLIM 1.2.8) validates
`commonInformationModels` against a built-in list that stops at CIM 4.5 and has
no `Change` model, so declaring CIM 5.x there would fail validation.

### Event types and tags

| Event type | Search | Tags |
|---|---|---|
| `genesyscloud_audit_change` | `sourcetype="genesyscloud:operational:audits"` | `change` |
| `genesyscloud_audit_account` | audits where the entity type is `User` (both key shapes) | `change`, `account` |
| `genesyscloud_edge_performance` | `sourcetype="genesyscloud:telephonyprovidersedge:edges:metrics"` | `performance`, `cpu`, `memory`, `os`, `uptime` |
| `genesyscloud_edge_storage` | edge metrics where `disks_total_bytes>0` | `performance`, `storage` |

In the Performance model, `Uptime` is a child of the `OS` dataset, so uptime
events also need the `os` tag and the OS-required `signature` field.

`Storage` has its own event type so that edge metrics indexed before the
upgrade, which lack the disk sums, stay out of the Storage dataset instead of
appearing there with empty fields.

### Audits → Change

Audit events reach Splunk in two key shapes:

- **snake_case** when the SDK returns model objects (`audit_query_helper.py`
  calls `entity.to_dict()`): `remote_ip`, `entity_type`, `service_name`,
  `user_home_org_id`, `property_changes`.
- **camelCase** when the results API redirects to a `downloadUrl` and the client
  downloads the raw file: `remoteIp`, `entityType`, `serviceName`,
  `userHomeOrgId`, `propertyChanges`.

Every mapping reads both forms, for example
`coalesce(entity_type, entityType)`. Below, only the camelCase name is shown.

| CIM field | Source |
|---|---|
| `action` | Normalized Genesys action (table below) |
| `command` | Raw Genesys action, e.g. `Update` |
| `status` | `SUCCESS` → `success`; `FAILURE` → `failure`; `WARNING` → `success` |
| `result` | `warning` when status is `WARNING`, otherwise `message.message` |
| `change_type` | `serviceName`, e.g. `Directory`, `Routing` |
| `object` | `entity.name`, falling back to `entity.id` |
| `object_id` | `entity.id` |
| `object_category` | `lower(entityType)` |
| `object_attrs` | `propertyChanges{}.property` (multivalue) |
| `user` | `user.name`, falling back to `user.id` (but see Account_Management) |
| `user_id` | `user.id` |
| `user_type` | `level` (`USER`, `SYSTEM`, `GENESYS_INTERNAL`) |
| `src` | `remoteIp{}` (multivalue) |
| `dest` | `userHomeOrgId` |
| `vendor_account` | `userHomeOrgId` |
| `dvc` | `Genesys Cloud` |
| `vendor` / `product` / `vendor_product` | `Genesys` / `Genesys Cloud` / `Genesys Cloud` |

The SDK models `action` as a free-form string, not an enum. Matching is
case-insensitive and unknown values fall back to `lower(action)` so they are
never dropped:

| Genesys action | CIM `action` |
|---|---|
| `Create` | `created` |
| `Update` | `updated` |
| `Delete`, `Purge` | `deleted` |
| `Read`, `View`, `Download`, `Export` | `read` |
| `Add`, `Remove`, `Move`, `Archive`, `Unarchive`, `Restore`, `Rotate`, `ChangePassword`, `Authorize`, `Deauthorize`, `Revoke` | `modified` |
| anything else | `lower(action)` |

**Account_Management.** When the entity type is `User`, CIM expects `user` to
be the account that was changed and `src_user` to be who changed it:

| CIM field | Source (entity type `User` only) |
|---|---|
| `user` | `entity.name`, falling back to `entity.id` |
| `src_user` | `user.name`, falling back to `user.id` |
| `src_user_name` | `user.name` |

### Edge metrics → Performance

Edge metric events are always SDK `to_dict()` output, so keys are snake_case
(`up_time_msec`, `processors{}.cpu_id`, `memory{}.total_bytes`).

| CIM field | Source |
|---|---|
| `dest` | `edge.name`, falling back to `edge.id` |
| `resource_type` | `system` |
| `vendor_product` | `Genesys Cloud` |
| `cpu_load_percent` | `active_time_pct` of the processor whose `cpu_id` is `total` |
| `cpu_user_percent` | `user_time_pct` of the processor whose `cpu_id` is `total` |
| `mem` | `total_bytes` of the `physical` memory entry, in MB |
| `mem_free` | `available_bytes` of the `physical` memory entry, in MB |
| `mem_used` | `mem - mem_free` |
| `uptime` | `up_time_msec / 1000` |
| `signature` | `edge_metrics` (static; required by the OS dataset) |
| `storage` | `disks_total_bytes`, in MB |
| `storage_free` | `disks_available_bytes`, in MB |
| `storage_used` | `storage - storage_free` |
| `storage_free_percent` | `storage_free / storage * 100` |
| `storage_used_percent` | `storage_used / storage * 100` |

CPU and memory entries are selected with
`mvindex(<values>, mvfind(<keys>, "^total$"))`, and likewise for `^physical$`.
MB means bytes / 1048576.

**Storage.** Splunk `eval` has no function that sums a multivalue field, so
`edges_metrics_helper.py` adds two top-level fields, `disks_total_bytes` and
`disks_available_bytes`, summed over `disks`. The summing lives on `EdgeModel`
in `genesyscloud_models.py`, which imports only the Genesys SDK, so it can be
unit-tested without the build-generated `import_declare_test`. No existing field is renamed or
removed, so existing searches keep working. Events indexed before the upgrade
have no disk sums, so they are not tagged `storage`; their CPU, Memory and
Uptime fields still map. When `disks` is empty or missing, both sums are `0`,
which also keeps the event out of the Storage dataset.

## Testing

### CIM compliance (new CI job)

`.github/workflows/cim.yml` runs pytest-splunk-addon **6.4.0**, pinned. It
runs as its own job, with its own `tests/knowledge/` directory, requirements
and `pytest.ini`, because the existing suite pins pytest 6.2.4.

Version 6.4.0 is the newest self-contained release. Releases 7.x and 8.x import
`splunk_cim_models`, which is not a declared dependency, is not on public PyPI,
and is sourced from a private Splunk repository; the PSA documentation warns
against installing a package by that name from PyPI. The models bundled in
6.4.0 predate that repository's `cim-6` branch, which matches a CIM 5.x target.

- Target a plain `splunk/splunk:10.2.0` container with the built add-on
  mounted. PSA validates CIM compliance from each dataset's tag constraints and
  required fields; it never runs `| datamodel`, so the CIM add-on is not
  installed. The job needs no Splunkbase credentials and runs on forks.
- Sample events live in `tests/knowledge/samples/` with a
  `pytest-splunk-addon-data.conf`, ingested over HEC (`input_type = modinput`):
  - audits in snake_case shape,
  - audits in camelCase (downloaded) shape,
  - an audit whose entity type is `User` (Account_Management),
  - edge metrics including `disks_total_bytes` and `disks_available_bytes`.
- The job passes when pytest-splunk-addon reports the Change and Performance
  CIM tests and field-extraction tests green for both sourcetypes.

### Unit test

A unit test for the `EdgeModel` disk-sum method covers several disks, an empty
list, and a missing `disks` key. It runs without Splunk or the mock API.

## Success criteria

- The pytest-splunk-addon CI job is green: the CIM required-field tests for
  Change (`All_Changes`, `Account_Management`) and Performance (`CPU`,
  `Memory`, `Storage`, `OS`, `Uptime`), plus the field, event type and tag
  tests for both sourcetypes, for both audit key shapes.
- With the CIM add-on installed, `| datamodel Change All_Changes search` and
  `| datamodel Performance CPU search` (and `Memory`, `Storage`, `Uptime`)
  return the sample events. This is a manual check documented in
  `docs/CIM/index.md`, not part of CI.
- The disk-sum unit test passes.
- The existing `tests` workflow stays green.
