import subprocess

import imageio_ffmpeg
from PIL import Image

from forge.assets import AssetManager, LocalAssetProvider
from forge.media import render


def _silent_mp3(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y",
        "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
        "-t", "1", "-q:a", "9", str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _tiny_video(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=80x140:d=2",
        "-pix_fmt", "yuv420p", str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def test_render_v2_with_local_asset(tmp_path):
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    Image.new("RGB", (80, 140), (30, 90, 140)).save(asset_dir / "autumn.jpg")
    _tiny_video(asset_dir / "ocean.mp4")

    out_dir = tmp_path / "media"
    _silent_mp3(out_dir / "seg" / "01.mp3")
    _silent_mp3(out_dir / "seg" / "02.mp3")
    _silent_mp3(out_dir / "seg" / "03.mp3")
    script = {
        "title": "测试视频",
        "cover_text": "测试",
        "segments": [
            {"heading": "开场", "text": "第一段口播内容", "caption": "第一段字幕",
             "visual_query": "autumn", "visual_type": "image"},
            {"heading": "中段", "text": "第二段口播内容", "caption": "第二段字幕",
             "visual_query": "ocean", "visual_type": "video"},
            {"heading": "结尾", "text": "第三段口播内容", "caption": "第三段字幕",
             "visual_query": "missing", "visual_type": "image"},
        ],
    }
    result = render(
        script,
        out_dir,
        size=(180, 320),
        bg=(12, 20, 38),
        accent=(99, 179, 255),
        fps=5,
        asset_manager=AssetManager([LocalAssetProvider(asset_dir)]),
    )
    assert (out_dir / "final.mp4").exists()
    assert (out_dir / "video_manifest.json").exists()
    assert (out_dir / "captions.srt").exists()
    assert (out_dir / "generation_manifest.json").exists()
    assert (out_dir / "visual_review.json").exists()
    assert result["segment_count"] == 3
