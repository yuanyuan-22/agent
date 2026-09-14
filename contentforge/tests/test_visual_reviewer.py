from forge.visual_reviewer import review_visuals


def test_visual_review_flags_video_fallback():
    scenes = [{
        "asset_policy": "generate_video",
        "visual_prompt": "test scene",
        "show_character": False,
        "asset": {"kind": "image", "provider": "siliconflow_image", "fingerprint": "x"},
    }]
    result = review_visuals(scenes)
    assert result["fallback_count"] == 1
    assert any("图生视频失败" in issue for issue in result["issues"])


def test_visual_review_passes_generated_video():
    scenes = [{
        "asset_policy": "generate_video",
        "visual_prompt": "test scene",
        "show_character": False,
        "asset": {"kind": "video", "provider": "siliconflow_video", "fingerprint": "x"},
    }]
    result = review_visuals(scenes)
    assert result["pass"] is True
    assert result["video_scenes"] == 1
