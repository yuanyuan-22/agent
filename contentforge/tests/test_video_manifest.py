from forge.video_manifest import build_manifest, write_manifest, write_srt


def test_video_manifest_and_srt(tmp_path):
    script = {"title": "测试", "cover_text": "封面"}
    scenes = [
        {"heading": "开场", "caption": "第一段", "text": "第一段口播", "duration": 2.5},
        {"heading": "结尾", "caption": "第二段", "text": "第二段口播", "duration": 3.0,
         "asset": {"kind": "image", "path": "a.jpg"}},
    ]
    manifest = build_manifest(script, scenes, out_dir=tmp_path, size=(1080, 1920), fps=24)
    assert manifest["duration"] == 5.5
    assert manifest["scenes"][1]["start"] == 2.5
    manifest_path = write_manifest(manifest, tmp_path)
    srt_path = write_srt(manifest, tmp_path)
    assert manifest_path.exists()
    assert "00:00:02,500 --> 00:00:05,500" in srt_path.read_text(encoding="utf-8")
