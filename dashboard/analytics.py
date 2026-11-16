"""Deterministic synthetic telemetry. Never presented as production measurements."""
import math
import random
from collections import Counter
from datetime import timedelta
from statistics import mean

FEATURES = ["Question generation", "Answer grading", "Mock interview", "Coach chat", "Resume reading", "Ask Beacon"]
PROVIDERS = ["Lumen", "Groq"]


def percentile(values, p):
    if not values:
        return 0
    values = sorted(values)
    pos = (len(values) - 1) * p
    return values[int(pos)] + (values[math.ceil(pos)] - values[int(pos)]) * (pos % 1)


def sample_data(today):
    rng = random.Random(490)
    rows = []
    for offset in range(30):
        day = today - timedelta(days=29-offset)
        for _ in range(rng.randint(65, 115)):
            feature = rng.randrange(6)
            chars = rng.randint(50, 6500 if feature == 4 else 2500)
            outcome = rng.choices(["Success", "Timeout", "Invalid JSON", "Provider down", "Slow mode"], [90, 3, 2, 2, 3])[0]
            prompt = chars // 4 + 180
            completion = rng.randint(80, 700)
            rows.append(dict(day=day.isoformat(), hour=rng.randrange(24), user=rng.randrange(1, 81),
                             feature=FEATURES[feature], provider=rng.choice(PROVIDERS),
                             cohort=rng.choice(["First week", "Later"]), input_chars=chars,
                             latency_ms=round(200 + chars * .28 + rng.lognormvariate(5.7, .65) + feature * 100),
                             outcome=outcome, tokens=prompt + completion,
                             cost=(prompt * .15 + completion * .60) / 1_000_000,
                             topic=rng.choice(["Readiness", "Practice", "Career goals", "Interview feedback", "Off topic"]),
                             low_grade=rng.random() < .25, retry=rng.random() < .58, returned=rng.random() < .69))
    return rows


def summarize(rows, today, days):
    n = len(rows)
    total_tokens = sum(r["tokens"] for r in rows)
    total_cost = sum(r["cost"] for r in rows)
    features = []
    overall = mean([r["latency_ms"] for r in rows]) if rows else 0
    for feature in FEATURES:
        group = [r for r in rows if r["feature"] == feature]
        count = len(group)
        features.append(dict(name=feature, count=count,
            p50=round(percentile([r["latency_ms"] for r in group], .5)),
            p95=round(percentile([r["latency_ms"] for r in group], .95)),
            shrunk=round((sum(r["latency_ms"] for r in group) + 20 * overall) / (count + 20)),
            first=sum(r["cohort"] == "First week" for r in group),
            later=sum(r["cohort"] == "Later" for r in group),
            tokens=round(sum(r["tokens"] for r in group)/count) if count else 0,
            cost=sum(r["cost"] for r in group)/count if count else 0,
            call_share=round(100*count/n, 1) if n else 0,
            token_share=round(100*sum(r["tokens"] for r in group)/total_tokens, 1) if total_tokens else 0))
    daily = []
    for offset in reversed(range(days)):
        day = (today-timedelta(days=offset)).isoformat()
        group = [r for r in rows if r["day"] == day]
        low = [r for r in group if r["low_grade"]]
        daily.append(dict(day=day, count=len(group), outcomes=dict(Counter(r["outcome"] for r in group)),
                          low_count=len(low), retry=100*sum(r["retry"] for r in low)/len(low) if low else None,
                          returned=100*sum(r["returned"] for r in low)/len(low) if low else None,
                          cost=sum(r["cost"] for r in group)))
    for i, day in enumerate(daily):
        window = daily[max(0, i-6):i+1]
        day["rolling"] = round(mean(d["count"] for d in window), 1)
        day["rolling_cost"] = mean(d["cost"] for d in window)
        day["rolling_fallback"] = 100 * sum(d["count"]-d["outcomes"].get("Success", 0) for d in window) / max(1, sum(d["count"] for d in window))
    asks = [r for r in rows if r["feature"] == "Ask Beacon"]
    topics = [dict(name=t, count=sum(r["topic"] == t for r in asks), declined=100 if t == "Off topic" else 0) for t in sorted({r["topic"] for r in asks})]
    hourly = Counter((r["day"], r["hour"]) for r in rows)
    user_hourly = Counter((r["day"], r["hour"], r["user"]) for r in rows)
    xs = [r["input_chars"] for r in rows]; ys = [r["latency_ms"] for r in rows]
    mx = mean(xs) if xs else 0; my = mean(ys) if ys else 0
    denom = math.sqrt(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
    return dict(count=n, active=len({r["user"] for r in rows}), features=features, daily=daily, topics=topics,
                fallback=round(100*sum(r["outcome"] != "Success" for r in rows)/n, 1) if n else 0,
                p95=round(percentile(ys, .95)), tokens=round(total_tokens/n) if n else 0,
                cost=total_cost, mean_cost=total_cost/n if n else 0, projected_cost=total_cost*10,
                peak=max(hourly.values(), default=0), user_peak=max(user_hourly.values(), default=0),
                correlation=round(sum((x-mx)*(y-my) for x,y in zip(xs,ys))/denom, 3) if denom else None,
                scatter=[dict(x=r["input_chars"], y=r["latency_ms"], feature=r["feature"]) for r in rows[::max(1,n//400)]],
                histogram=[sum(low <= y < low+500 for y in ys) for low in range(0, 10000, 500)])
