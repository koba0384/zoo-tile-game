
ANIMAL_POINTS = {
    "lion": 6,
    "elephant": 3,
    "giraffe": 2,
    "hippo": 2,
    "chimpanzee": 2,
    "flamingo": 1,
}

ANIMAL_LABELS = {
    "lion": "ライオン",
    "elephant": "ゾウ",
    "giraffe": "キリン",
    "hippo": "カバ",
    "chimpanzee": "チンパンジー",
    "flamingo": "フラミンゴ",
}

def score_animals(animals):
    details = []
    score = 0

    lion_count = animals.count("lion")
    non_lion_types = {a for a in animals if a != "lion"}
    if lion_count:
        lion_score = 0 if non_lion_types else ANIMAL_POINTS["lion"] * lion_count
        score += lion_score
        details.append({
            "label": "ライオン",
            "score": lion_score,
            "note": "単独飼育なら6点ずつ、他種がいたら0点",
        })

    for animal in ["elephant", "giraffe", "hippo", "chimpanzee", "flamingo"]:
        count = animals.count(animal)
        if count:
            pts = ANIMAL_POINTS[animal] * count
            score += pts
            details.append({
                "label": ANIMAL_LABELS[animal],
                "score": pts,
                "note": f"{count}枚",
            })

    return score, details

def score_combos(animals):
    details = []
    score = 0
    animal_types = set(animals)

    if "flamingo" in animal_types and "giraffe" in animal_types:
        score += 3
        details.append({"label": "仲良しポイント", "score": 3, "note": "フラミンゴ+キリン"})

    if {"giraffe", "elephant", "flamingo"}.issubset(animal_types):
        score += 5
        details.append({"label": "サバンナポイント", "score": 5, "note": "キリン+ゾウ+フラミンゴ"})

    if "chimpanzee" in animal_types and len(animal_types) >= 3:
        score += 2
        details.append({"label": "にぎやかポイント", "score": 2, "note": "チンパンジー + 3種類以上"})

    if animals.count("hippo") >= 2:
        score += 3
        details.append({"label": "群れポイント", "score": 3, "note": "カバ2頭以上"})

    return score, details

def score_region(animals, region_size, nested_bonus=0, completed=True):
    animal_score, animal_details = score_animals(animals)
    combo_score, combo_details = (0, [])
    completion_bonus = 0

    if completed:
        combo_score, combo_details = score_combos(animals)
        completion_bonus = region_size

    total = animal_score + combo_score + completion_bonus + nested_bonus
    breakdown = {
        "animal_score": animal_score,
        "animal_details": animal_details,
        "combo_score": combo_score,
        "combo_details": combo_details,
        "completion_bonus": completion_bonus,
        "nested_bonus": nested_bonus,
        "total": total,
        "completed": completed,
    }
    return total, breakdown
