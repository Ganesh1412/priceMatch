# Camunda Agent Pipeline

`price-match-agent-pipeline.bpmn` is an executable Camunda 8 process for the five existing agent roles. Deploy the file to a Camunda 8 cluster, then start `price-match-agent-pipeline` with these variables:

```json
{
  "product": "Apple AirPods Pro 3",
  "customer_price": "150",
  "zipcode": "10001"
}
```

Each service task maps to one worker job type. Workers should complete jobs by returning the named `*_result` variable; the BPMN output mapping stores it under the matching `*_output` process variable.

| Agent | Job type | Worker result | Stored process variable |
| --- | --- | --- | --- |
| Researcher | `price-match.researcher` | `research_result` | `researcher_output` |
| Solution Designer | `price-match.solution-designer` | `designer_result` | `designer_output` |
| Prototyper | `price-match.prototyper` | `prototyper_result` | `prototyper_output` |
| Communicator | `price-match.communicator` | `communicator_result` | `communicator_output` |
| Manager | `price-match.manager` | `manager_result` | `manager_output` |

The manager worker must set `manager_result.decision`. The process moves to the human-review task only when that value is `proceed_with_conditions` and `designer_output.disambiguation.status` is `confirmed`. All other outcomes end at `Held for validation`, preventing automated approval.

Each worker has three retries. A worker should raise a business error or use an incident for unrecoverable source failures instead of returning unsupported claims. This BPMN definition is orchestration only; it does not replace the existing FastAPI streamed endpoint until job workers are deployed and that endpoint is deliberately connected to Camunda.