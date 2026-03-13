def compute_composite(similarity, required, candidate, mcq, coding):
    required=set(map(str.lower,required))
    candidate=set(map(str.lower,candidate))

    skill_score=(len(required & candidate)/len(required))*100 if required else 100

    composite=(
        similarity*0.25+
        skill_score*0.20+
        mcq*0.20+
        coding*0.35
    )

    if composite>=75:
        rec="Strong Shortlist"
    elif composite>=60:
        rec="Shortlist"
    elif composite>=50:
        rec="Borderline"
    else:
        rec="Reject"

    return {
        "composite_score":round(composite,2),
        "recommendation":rec
    }
