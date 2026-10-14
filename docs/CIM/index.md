# CIM compatibility

The Genesys Cloud Add-on for Splunk is compatible with the [Splunk Common Information Model (CIM)](https://docs.splunk.com/Documentation/CIM/5.0.0) 5.x. Audit events populate the **Change** data model and edge metrics populate the **Performance** data model, so CIM-based searches, dashboards and Splunk Enterprise Security content work with Genesys Cloud data.

The mappings are search-time only, so they also apply to events indexed before the upgrade.

| Sourcetype | Data model | Datasets |
|---|---|---|
| `genesyscloud:operational:audits` | Change | `All_Changes`, `Account_Management` |
| `genesyscloud:telephonyprovidersedge:edges:metrics` | Performance | `CPU`, `Memory`, `Storage`, `OS`, `Uptime` |

The other sourcetypes carry contact-center metrics, such as MOS scores, routing statuses and queue observations, that no CIM data model describes. They are not mapped.

## Event types and tags

| Event type | Events | Tags |
|---|---|---|
| `genesyscloud_audit_change` | All audit events | `change` |
| `genesyscloud_audit_account` | Audit events on a `User` entity | `change`, `account` |
| `genesyscloud_edge_performance` | All edge metrics | `performance`, `cpu`, `memory`, `os`, `uptime` |
| `genesyscloud_edge_storage` | Edge metrics that include `disks_total_bytes` | `performance`, `storage` |

## Change

| CIM field | Value |
|---|---|
| `action` | Genesys Cloud action normalized to CIM: `Create` is `created`, `Update` is `updated`, `Delete` and `Purge` are `deleted`, `Read`, `View`, `Download` and `Export` are `read`, other changes such as `Add`, `Remove` or `Move` are `modified`. Any other action is lowercased. |
| `command` | Genesys Cloud action, e.g. `Update` |
| `status` | `success` or `failure`. `WARNING` maps to `success` with `result=warning`. |
| `result` | `warning`, or the audit message |
| `change_type` | Genesys Cloud service, e.g. `Directory`, `Routing` |
| `object`, `object_id` | Name and ID of the changed entity |
| `object_category` | Entity type in lowercase, e.g. `queue`, `user` |
| `object_attrs` | Names of the changed properties |
| `user`, `user_id`, `user_type` | User who made the change and its level (`USER`, `SYSTEM`, `GENESYS_INTERNAL`) |
| `src` | Remote IP address of the request |
| `dest`, `vendor_account` | Genesys Cloud organization ID |
| `dvc`, `vendor_product` | `Genesys Cloud` |

For changes to a user account (`Account_Management`), `user` is the account that was changed and `src_user` is the user who changed it, as CIM requires.

## Performance

| CIM field | Value |
|---|---|
| `dest` | Edge name |
| `cpu_load_percent`, `cpu_user_percent` | Active and user CPU time of the `total` processor |
| `mem`, `mem_free`, `mem_used` | Physical memory, in MB |
| `storage`, `storage_free`, `storage_used` | Capacity summed over all the edge disks, in MB |
| `storage_free_percent`, `storage_used_percent` | Percentages of the summed disk capacity |
| `uptime` | Edge uptime, in seconds |
| `signature` | `edge_metrics` |
| `resource_type` | `system` |

The disk sums (`disks_total_bytes`, `disks_available_bytes`) are added to each event by the **Edges Metrics** input. Edge metrics indexed by an earlier version of the add-on don't have them, so they are not part of the `Storage` dataset. Their CPU, memory and uptime are still mapped.

## Validate the mappings

With the [Splunk Common Information Model add-on](https://splunkbase.splunk.com/app/1621) installed, run the following searches. Each one should return Genesys Cloud events with the CIM fields above.

```
| datamodel Change All_Changes search | search sourcetype="genesyscloud:operational:audits"
| datamodel Change Account_Management search | search sourcetype="genesyscloud:operational:audits"
| datamodel Performance CPU search | search sourcetype="genesyscloud:telephonyprovidersedge:edges:metrics"
| datamodel Performance Memory search | search sourcetype="genesyscloud:telephonyprovidersedge:edges:metrics"
| datamodel Performance Storage search | search sourcetype="genesyscloud:telephonyprovidersedge:edges:metrics"
| datamodel Performance Uptime search | search sourcetype="genesyscloud:telephonyprovidersedge:edges:metrics"
```
