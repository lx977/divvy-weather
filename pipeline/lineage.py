"""Minimal OpenLineage helper: every pipeline step is wrapped in
`lineage_run(...)`, which records a START and a COMPLETE (or FAIL) event
with the step's input and output datasets, their schemas, and row counts.

Events are appended to `lineage_events.jsonl`. `send_to_marquez.py`
replays them into Marquez, which draws the lineage graph.
"""
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from openlineage.client.event_v2 import (InputDataset, Job, OutputDataset,
                                         Run, RunEvent, RunState)
from openlineage.client.facet_v2 import (documentation_job,
                                         output_statistics_output_dataset,
                                         schema_dataset)
from openlineage.client.serde import Serde

NAMESPACE = "divvy_weather_reporting"   # job namespace in Marquez
DATA_NS = "file://hw1"                   # dataset namespace (local files)
PRODUCER = "https://github.com/linx5/mlops-hw1-partb"
EVENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "lineage_events.jsonl")


def _schema(df):
    """OpenLineage schema facet from a pandas dataframe."""
    fields = [schema_dataset.SchemaDatasetFacetFields(name=str(c),
                                                      type=str(t))
              for c, t in df.dtypes.items()]
    return {"schema": schema_dataset.SchemaDatasetFacet(fields=fields)}


def now():
    """Current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _emit(event):
    with open(EVENTS_FILE, "a", encoding="utf-8") as fh:
        fh.write(Serde.to_json(event) + "\n")


@contextmanager
def lineage_run(job_name, description, inputs, outputs):
    """Wrap one pipeline step.

    inputs / outputs: lists of dataset names (paths relative to HW1/).
    The body can fill ctx["schemas"][name] = dataframe to attach output
    schemas + row counts, ctx["input_schemas"][name] likewise, and
    ctx["row_counts"][name] = n to override the row count.
    """
    run = Run(runId=str(uuid4()))
    job = Job(namespace=NAMESPACE, name=job_name, facets={
        "documentation": documentation_job.DocumentationJobFacet(
            description=description)})
    _emit(RunEvent(eventType=RunState.START, eventTime=now(), run=run,
                   job=job, producer=PRODUCER,
                   inputs=[InputDataset(namespace=DATA_NS, name=n)
                           for n in inputs],
                   outputs=[OutputDataset(namespace=DATA_NS, name=n)
                            for n in outputs]))
    ctx = {"schemas": {}, "input_schemas": {}, "row_counts": {}}
    try:
        yield ctx
    except Exception:
        _emit(RunEvent(eventType=RunState.FAIL, eventTime=now(), run=run,
                       job=job, producer=PRODUCER))
        raise

    def out_facets(name):
        df = ctx["schemas"].get(name)
        if df is None:
            return {}
        return _schema(df)

    def out_stats(name):
        df = ctx["schemas"].get(name)
        if df is None:
            return {}
        rows = ctx["row_counts"].get(name, len(df))
        return {"outputStatistics":
                output_statistics_output_dataset
                .OutputStatisticsOutputDatasetFacet(rowCount=rows)}

    _emit(RunEvent(
        eventType=RunState.COMPLETE, eventTime=now(), run=run, job=job,
        producer=PRODUCER,
        inputs=[InputDataset(namespace=DATA_NS, name=n,
                             facets=(_schema(ctx["input_schemas"][n])
                                     if n in ctx["input_schemas"] else {}))
                for n in inputs],
        outputs=[OutputDataset(namespace=DATA_NS, name=n,
                               facets=out_facets(n),
                               outputFacets=out_stats(n))
                 for n in outputs]))
