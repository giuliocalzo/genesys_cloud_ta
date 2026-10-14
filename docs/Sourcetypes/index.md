# Source types for the Genesys Cloud Add-on

The Genesys Cloud Add-on for Splunk provides the index-time and search-time knowledge for metrics, service status, and service message events in the following formats.

| Sourcetype | Description | CIM data model |
|:---:|---|---|
| `genesyscloud:telephonyprovidersedge:edges:metrics`  | All the metrics for edges  | [Performance](../CIM/index.md#performance) |
| `genesyscloud:telephonyprovidersedge:edges:phones`  | All phones statuses  | |
| `genesyscloud:telephonyprovidersedge:trunks:metrics` | All the metrics for trunks | |
| `genesyscloud:analytics:actions:metrics` | All the metrics for actions aggregated by `actionId` | |
| `genesyscloud:analytics:conversations:details` | All the score metrics for conversations, e.g., MOS scores | |
| `genesyscloud:analytics:flows:metrics` | All the metrics for conversations | |
| `genesyscloud:analytics:queues:observations` | All the metrics for queue observations | |
| `genesyscloud:users:users:aggregates` | All the metrics for user aggregates | |
| `genesyscloud:users:users:routingstatus` | All the user routing statuses | |
| `genesyscloud:operational:audits` | All the audit events | [Change](../CIM/index.md#change) |
| `genesyscloud:operational:system` | All Genesys Cloud system services status retrieved via [Status Page API](https://metastatuspage.com/api#summary) | |
