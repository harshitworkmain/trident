"""SOS triage: a 0-100 score with human-readable reasons, mapped to priority P1 (most urgent) to P5.

Replaces the old additive 1-5 counter, which saturated at 5 for most real requests and could not
say why. Points are capped per factor so no single field dominates; a linked wearable in a
critical fusion state (Tier-2) adds the largest single contribution because it is measured,
not self-reported.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

TYPE_POINTS = {'tsunami': 25, 'dam-breach': 25, 'flood': 15, 'storm': 12, 'water-level-rising': 12,
               'medical': 15, 'coastal-erosion': 5, 'other': 5}
SUPPLY_POINTS = {'none': 10, 'critical': 7, 'limited': 2, 'adequate': 0}
VULNERABILITY_POINTS = {'medical': 12, 'pregnant': 8, 'elderly': 6, 'children': 6, 'disabled': 8}
PRIORITY_BANDS = (15, 30, 45, 60)          # score >= 60 -> P1 ... < 15 -> P5 (a measured critical wearable state alone adds 30)


AGEING_POINTS_PER_5_MIN, AGEING_CAP = 2, 20      # anti-starvation: waiting requests climb the queue


def score(sos: dict, device: Optional[dict] = None, waiting_min: float = 0.0) -> Tuple[int, int, List[str]]:
    """(priority P1-P5, 1 = most urgent; score 0-100; reasons) for an SOS dict and an optional device summary."""
    pts, reasons = 0, []

    def add(p: int, why: str):
        nonlocal pts
        if p > 0:
            pts += p
            reasons.append(why)

    if sos.get('source') == 'wearable':
        add(40, 'SOS button pressed on wearable')     # deliberate, from someone who may have no phone: P2 or above
    t = sos.get('emergency_type', 'other')
    add(TYPE_POINTS.get(t, 5), f'{t.replace("-", " ")} emergency')
    injured = int(sos.get('people_injured', 0))
    if injured:
        add(min(25, 10 + 5 * (injured - 1)), f'{injured} injured')
    people = int(sos.get('people_to_rescue', 1))
    if people > 1:
        add(min(10, 2 * (people - 1)), f'{people} people to rescue')
    vul = sos.get('vulnerabilities') or {}
    for k, p in VULNERABILITY_POINTS.items():
        if vul.get(k):
            add(p, {'medical': 'medical need'}.get(k, k))
    water, food = sos.get('water_availability', 'adequate'), sos.get('food_availability', 'adequate')
    add(SUPPLY_POINTS.get(water, 0), f'water {water}')
    add(SUPPLY_POINTS.get(food, 0) // 2, f'food {food}')
    age = sos.get('age')
    if age is not None and (int(age) >= 70 or int(age) <= 5):
        add(4, f'age {age}')
    if device:
        level, state = device.get('alert_level'), device.get('ml_health_state', 'STABLE')
        if level == 'critical':
            add(30, f'wearable: {state}')
        elif level == 'advisory':
            add(5, f'wearable: {state}')
        if device.get('online') is False:
            add(3, 'wearable offline')
    if waiting_min >= 5:
        add(min(AGEING_CAP, AGEING_POINTS_PER_5_MIN * int(waiting_min // 5)), f'waiting {int(waiting_min)} min')
    total = min(100, pts)
    priority = 5 - sum(total >= b for b in PRIORITY_BANDS)
    return priority, total, reasons
