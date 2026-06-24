from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    unit: str
    value_type: type


METRIC_REGISTRY: dict[str, MetricDefinition] = {
    "reps":        MetricDefinition("reps",        "",     int),
    "weight":      MetricDefinition("weight",      "kg",   float),
    "time":        MetricDefinition("time",        "s",    int),
    "time_min":    MetricDefinition("time",        "min",  int),
    "distance":    MetricDefinition("distance",    "m",    float),
    "thigh2floor": MetricDefinition("thigh2floor", "cm",   float),
    "knee2floor":  MetricDefinition("knee2floor",  "cm",   float),
    "feet2floor":  MetricDefinition("feet2floor",  "cm",   float),
}


def get_metric(name: str) -> MetricDefinition:
    if name not in METRIC_REGISTRY:
        raise KeyError(f"Unknown metric: {name!r}")
    return METRIC_REGISTRY[name]


def format_metric_prompt(metric_names: list[str]) -> str:
    parts = []
    for name in metric_names:
        defn = METRIC_REGISTRY[name]
        if defn.unit:
            parts.append(f"<{name}({defn.unit})>")
        else:
            parts.append(f"<{name}>")
    return " ".join(parts)
