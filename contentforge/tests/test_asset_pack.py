from forge.asset_pack import build_asset_pack, load_asset_pack, write_asset_pack


def test_asset_pack_exports_json_and_markdown(tmp_path):
    pack = build_asset_pack(
        job_id="asset1",
        video={
            "platform": "douyin",
            "source_id": "123",
            "source_url": "https://v.douyin.com/abc/",
            "title": "桂林火车票盲盒",
            "owner": "iio",
            "transcript_mode": "share_text",
            "transcript_text": "博主购买高铁盲盒后前往广西桂林。",
        },
        dna={
            "topic": "高铁盲盒旅行",
            "facts": [
                {"claim": "博主购买了高铁盲盒", "evidence": "购买高铁盲盒"},
            ],
        },
        ideas=[{"title": "盲盒开出桂林", "hook": "一张盲盒票会开到哪里？"}],
        selected_idea={"title": "盲盒开出桂林"},
        script={
            "title": "一张盲盒票开到了桂林",
            "cover_text": "盲盒直达桂林",
            "description": "记录一次高铁盲盒旅行。",
            "tags": ["旅行", "盲盒"],
            "segments": [{"heading": "出发", "text": "从一张未知车票开始。", "caption": "未知目的地"}],
        },
        storyboard={"scenes": [{"shot_id": 1, "caption": "未知目的地"}]},
        review={"pass": True, "score": 8.5, "topic_consistency": 9, "fact_support": 8},
    )

    paths = write_asset_pack(pack, tmp_path)
    loaded = load_asset_pack(paths["json"])
    markdown = (tmp_path / "content_assets.md").read_text(encoding="utf-8")

    assert loaded["selected_script"]["title"] == "一张盲盒票开到了桂林"
    assert "高铁盲盒旅行" in markdown
    assert "博主购买了高铁盲盒" in markdown
    assert loaded["artifacts"]["asset_pack_json"] == paths["json"]
