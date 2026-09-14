from forge.visual_policy import apply_visual_policy, choose_video_scene_indexes


def _scenes():
    return [
        {"shot_id": i + 1, "purpose": p, "importance": imp}
        for i, (p, imp) in enumerate([
            ("hook", 0.95),
            ("body", 0.4),
            ("body", 0.5),
            ("reveal", 0.9),
            ("body", 0.45),
            ("cta", 0.85),
        ])
    ]


def test_choose_video_scenes_prefers_hook_reveal_cta():
    indexes = choose_video_scene_indexes(_scenes(), "balanced")
    assert indexes == [0, 3, 5]


def test_apply_visual_policy_sets_asset_policy():
    scenes = apply_visual_policy(_scenes(), "balanced")
    assert sum(1 for s in scenes if s["asset_policy"] == "generate_video") == 3
    assert all("visual_type" in s for s in scenes)
