# GitHub Actions status on 2026-08-26

Date checked: 2026-08-26 18:01 UTC (21:01 Europe/Moscow)  
Scope: GitHub's official [current status](https://www.githubstatus.com/api/v2/status.json), [component summary](https://www.githubstatus.com/api/v2/summary.json), [incident API](https://www.githubstatus.com/api/v2/incidents.json), and [incident history](https://www.githubstatus.com/history)

## Conclusion

GitHub Actions did have a critical incident today. GitHub recorded the incident from 15:11:58 UTC until 18:01:30 UTC (18:11:58–21:01:30 Europe/Moscow), marked the Actions component as a major outage during the incident, restored the component to operational at 17:54:33 UTC, and marked the incident resolved at 18:01:30 UTC ([official incident API](https://www.githubstatus.com/api/v2/incidents.json)).

At the time of this check, GitHub reports **All Systems Operational**, the Actions component is `operational`, and the current summary contains no active incidents ([current status API](https://www.githubstatus.com/api/v2/status.json), [component summary API](https://www.githubstatus.com/api/v2/summary.json)). Work that depends on new Actions runs can therefore resume; this is a current-status conclusion, not a guarantee against a later recurrence.

## What was affected

- GitHub initially reported degraded availability for Actions and changed the component from `operational` to `major_outage` at 15:11:58 UTC ([official incident API](https://www.githubstatus.com/api/v2/incidents.json)).
- GitHub Pages was also marked as experiencing degraded performance at 15:12:21 UTC. Pages returned to `operational` at 16:49:07 UTC, before Actions fully recovered ([official incident API](https://www.githubstatus.com/api/v2/incidents.json)).
- During recovery, GitHub reported delayed inbound Actions queues and throttled work; it expected the queues to return to normal within 30 minutes as processing continued under per-customer concurrency limits ([official incident API](https://www.githubstatus.com/api/v2/incidents.json)).
- At 18:00:48 UTC, GitHub said all inbound queues had recovered and Actions was operating as expected. It also reported that 3.7% of jobs assigned to larger runners during the incident's early stage were still waiting for runner assignment and would be canceled within the hour, while other runners were processing all new jobs successfully ([official incident API](https://www.githubstatus.com/api/v2/incidents.json)).

## Recovery timeline

| Time (UTC) | Official update |
|---|---|
| 15:11:58 | Actions investigation opened; component changed to `major_outage` ([incident API](https://www.githubstatus.com/api/v2/incidents.json)). |
| 15:23:10 | GitHub identified a database-primary issue and began failing over to a replica ([incident API](https://www.githubstatus.com/api/v2/incidents.json)). |
| 15:48:07 | GitHub said the primary failover had only briefly improved performance, throttled inbound traffic, and was investigating upstream Vitess issues ([incident API](https://www.githubstatus.com/api/v2/incidents.json)). |
| 16:14:16 | GitHub said it had identified and addressed the issue and was gradually restoring traffic; some customers would continue to see delays during ramp-up ([incident API](https://www.githubstatus.com/api/v2/incidents.json)). |
| 16:49:07 | Pages returned to normal while Actions remained a major outage ([incident API](https://www.githubstatus.com/api/v2/incidents.json)). |
| 17:54:33 | GitHub marked the Actions degradation mitigated, changed Actions back to `operational`, and began monitoring ([incident API](https://www.githubstatus.com/api/v2/incidents.json)). |
| 18:00:48 | GitHub reported recovered inbound queues and normal processing of new jobs except for the residual larger-runner jobs described above ([incident API](https://www.githubstatus.com/api/v2/incidents.json)). |
| 18:01:30 | GitHub marked the incident resolved ([incident API](https://www.githubstatus.com/api/v2/incidents.json)). |

## Cause status

GitHub's live updates identified a database-primary problem, an incomplete failover mitigation, and upstream Vitess issues during the response ([official incident API](https://www.githubstatus.com/api/v2/incidents.json)). These are incident-time findings rather than a final root-cause account: the resolution notice explicitly says that a detailed root cause analysis will be shared later ([official incident API](https://www.githubstatus.com/api/v2/incidents.json)).

## Operational decision for Wardrowbe

Proceed with GitHub Actions maintenance and verification now because the official current APIs report Actions operational and no active incident ([current status API](https://www.githubstatus.com/api/v2/status.json), [component summary API](https://www.githubstatus.com/api/v2/summary.json)). If an older larger-runner job remains queued or becomes canceled, rerun it rather than treating that residual job as evidence that the current service is still down, consistent with GitHub's final recovery update ([official incident API](https://www.githubstatus.com/api/v2/incidents.json)).
