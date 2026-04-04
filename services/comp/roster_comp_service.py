from data.signup_store import load_signups, find_message_signup


def _get_display_role(entry: dict) -> str:
    role = entry.get("role", "")

    if role in ("Melee", "Ranged"):
        return "DPS"

    return role


def _sort_by_timestamp(players: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    return sorted(players, key=lambda item: item[1].get("timestamp", 0))


def _empty_status_buckets() -> dict[str, list[tuple[str, dict]]]:
    return {
        "sign": [],
        "bench": [],
        "late": [],
        "tentative": [],
        "absence": [],
    }


def _split_players(users: dict) -> dict[str, list[tuple[str, dict]]]:
    """
    Split all signup users into status buckets.

    Important:
    - Only `sign` is used to build the actual raid comp.
    - The other buckets are preserved so the posted comp snapshot
      contains enough information for future attendance automation.
    """
    buckets = _empty_status_buckets()

    for user_id, entry in users.items():
        status = entry.get("status")
        player = (str(user_id), entry)

        if status in buckets:
            buckets[status].append(player)

    for key in buckets:
        buckets[key] = _sort_by_timestamp(buckets[key])

    return buckets


def _group_signed_players(players: list[tuple[str, dict]]) -> dict[str, list[tuple[str, dict]]]:
    grouped = {
        "Tank": [],
        "Healer": [],
        "DPS": [],
    }

    for user_id, entry in players:
        display_role = _get_display_role(entry)
        if display_role in grouped:
            grouped[display_role].append((user_id, entry))

    return grouped


def _build_comp_option(
    grouped: dict[str, list[tuple[str, dict]]],
    *,
    healer_count: int,
    dps_count: int,
    label: str,
) -> dict:
    tanks = grouped["Tank"][:2]
    healers = grouped["Healer"][:healer_count]
    dps = grouped["DPS"][:dps_count]

    selected = tanks + healers + dps

    return {
        "label": label,
        "tanks": tanks,
        "healers": healers,
        "dps": dps,
        "selected": selected,
        "selected_ids": {user_id for user_id, _ in selected},
        "count": len(selected),
        "role_targets": {
            "Tank": 2,
            "Healer": healer_count,
            "DPS": dps_count,
        },
    }


def _build_groups(comp: dict) -> tuple[list[tuple[str, dict]], list[tuple[str, dict]]]:
    group_1 = []
    group_2 = []

    group_1.extend(comp["tanks"])
    group_1.extend(comp["healers"])

    remaining_dps = list(comp["dps"])

    while len(group_1) < 5 and remaining_dps:
        group_1.append(remaining_dps.pop(0))

    group_2.extend(remaining_dps)

    return group_1, group_2


def _get_bench_choice_steps(
    grouped: dict[str, list[tuple[str, dict]]],
    role_targets: dict[str, int],
) -> list[dict]:
    """
    Returns a list of manual bench selection steps.

    Example:
    - signed Healers = 3, target Healers = 2
    - signed DPS = 7, target DPS = 6

    returns:
    [
        {"role": "Healer", "count_to_bench": 1, "candidates": [...]},
        {"role": "DPS", "count_to_bench": 1, "candidates": [...]},
    ]
    """
    steps = []

    for role_name in ("Healer", "DPS"):
        signed_count = len(grouped[role_name])
        target_count = role_targets.get(role_name, 0)

        if signed_count > target_count:
            steps.append(
                {
                    "role": role_name,
                    "count_to_bench": signed_count - target_count,
                    "candidates": list(grouped[role_name]),
                }
            )

    return steps


def _build_comp_payload(
    signup: dict,
    raid_id: int | str,
    status_buckets: dict[str, list[tuple[str, dict]]],
    grouped_signed: dict[str, list[tuple[str, dict]]],
    comp: dict,
) -> dict:
    signed_players = status_buckets["sign"]
    existing_bench = status_buckets["bench"]
    late_players = status_buckets["late"]
    tentative_players = status_buckets["tentative"]
    absence_players = status_buckets["absence"]

    bench_choice_steps = _get_bench_choice_steps(
        grouped_signed,
        comp["role_targets"],
    )

    # If manual selection is needed for any role, do not auto-bench overflow yet.
    if bench_choice_steps:
        overflow_signed = []
    else:
        overflow_signed = [
            (user_id, entry)
            for user_id, entry in signed_players
            if user_id not in comp["selected_ids"]
        ]

    bench_players = existing_bench + overflow_signed
    group_1, group_2 = _build_groups(comp)

    return {
        "raid_id": str(raid_id),
        "title": signup.get("title", "Raid Comp"),
        "description": signup.get("description", ""),
        "leader": signup.get("leader", ""),
        "start_ts": signup.get("start_ts"),
        "group_1": group_1,
        "group_2": group_2,
        "bench_players": bench_players,
        "late_players": late_players,
        "tentative_players": tentative_players,
        "absence_players": absence_players,
        "selected_players": comp["selected"],
        "signed_players": signed_players,
        "mentions": [f"<@{user_id}>" for user_id, _ in comp["selected"]],
        "comp_label": comp["label"],
        "role_targets": comp["role_targets"],
        "bench_choice_steps": bench_choice_steps,
        "status_buckets": {
            "sign": signed_players,
            "bench": bench_players,
            "late": late_players,
            "tentative": tentative_players,
            "absence": absence_players,
        },
    }


def analyze_roster_comp(raid_id: int | str) -> tuple[str, dict | None]:
    """
    Returns:
    - ("ready", {"comp_data": ...}) when one comp should be posted directly
    - ("ambiguous", {"option_226": ..., "option_235": ...}) when both are valid 10-man comps
    - ("error", None) when raid not found
    """
    data = load_signups()
    signup = find_message_signup(data, raid_id)

    if not signup:
        return "error", None

    users = signup.get("users", {})
    status_buckets = _split_players(users)
    signed_players = status_buckets["sign"]
    grouped = _group_signed_players(signed_players)

    option_226 = _build_comp_option(
        grouped,
        healer_count=2,
        dps_count=6,
        label="2/2/6",
    )

    option_235 = _build_comp_option(
        grouped,
        healer_count=3,
        dps_count=5,
        label="2/3/5",
    )

    if option_226["count"] > option_235["count"]:
        return "ready", {
            "comp_data": _build_comp_payload(
                signup,
                raid_id,
                status_buckets,
                grouped,
                option_226,
            )
        }

    if option_235["count"] > option_226["count"]:
        return "ready", {
            "comp_data": _build_comp_payload(
                signup,
                raid_id,
                status_buckets,
                grouped,
                option_235,
            )
        }

    both_full_ten = option_226["count"] == 10 and option_235["count"] == 10
    setups_differ = option_226["label"] != option_235["label"]

    if both_full_ten and setups_differ:
        return "ambiguous", {
            "option_226": _build_comp_payload(
                signup,
                raid_id,
                status_buckets,
                grouped,
                option_226,
            ),
            "option_235": _build_comp_payload(
                signup,
                raid_id,
                status_buckets,
                grouped,
                option_235,
            ),
        }

    return "ready", {
        "comp_data": _build_comp_payload(
            signup,
            raid_id,
            status_buckets,
            grouped,
            option_226,
        )
    }