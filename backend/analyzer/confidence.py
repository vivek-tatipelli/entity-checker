def enrich_confidence(entity, source_count: int = 1):
    score = entity.confidence
    props = entity.properties

    if props.get("name"):
        score += 0.05
    if props.get("url"):
        score += 0.05
    if props.get("sameAs"):
        score += 0.05
    if props.get("logo"):
        score += 0.03

    if source_count > 1:
        score += 0.1

    entity.confidence = round(min(score, 1.0), 2)
