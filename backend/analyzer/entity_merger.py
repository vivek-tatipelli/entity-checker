from collections import defaultdict

def _identity_key(entity):
    props = entity.properties
    return (
        entity.type,
        props.get("name", "").lower(),
        props.get("url", "").lower()
    )


def merge_entities(entities):
    buckets = defaultdict(list)

    for e in entities:
        buckets[_identity_key(e)].append(e)

    merged = []

    for _, group in buckets.items():
        primary = max(group, key=lambda x: x.confidence)

        # merge sources
        primary.source = ",".join(sorted(set(e.source for e in group)))

        # confidence boost for multi-source
        if len(group) > 1:
            primary.confidence = min(primary.confidence + 0.1, 1.0)

        merged.append(primary)

    return merged
