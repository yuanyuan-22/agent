from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import Column, Float, Integer, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from forge.config import settings

Base = declarative_base()
_db_path = settings.data_dir / "forge.db"
engine = create_engine(
    f"sqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Text, primary_key=True)
    source = Column(Text, default="")
    channel = Column(Text, default="bilibili")
    target_platforms = Column(Text, default='["bilibili"]')
    visual_style = Column(Text, default="tech_infographic")
    generation_mode = Column(Text, default="balanced")
    character_id = Column(Text, default="host_default")
    review_status = Column(Text, default="pending")
    asset_pack_path = Column(Text, default="")
    status = Column(Text, default="pending")
    run_dir = Column(Text, default="")
    title = Column(Text, default="")
    style = Column(Text, default="")
    manual_review = Column(Integer, default=0)
    error = Column(Text, default="")
    result = Column(Text, default="{}")
    published = Column(Integer, default=0)
    own_bvid = Column(Text, default="")
    published_at = Column(Text, default="")
    publish_records = Column(Text, default="{}")
    created_at = Column(Text, default=_now)
    updated_at = Column(Text, default=_now)


class JobEvent(Base):
    __tablename__ = "job_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Text, index=True)
    kind = Column(Text, default="")
    message = Column(Text, default="")
    payload = Column(Text, default="{}")
    ts = Column(Text, default=_now)


class JobMetric(Base):
    __tablename__ = "job_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Text, index=True)
    platform = Column(Text, default="bilibili")
    captured_at = Column(Text, default=_now)
    view = Column(Integer, default=0)
    like = Column(Integer, default=0)
    coin = Column(Integer, default=0)
    share = Column(Integer, default=0)
    favorite = Column(Integer, default=0)
    danmaku = Column(Integer, default=0)
    reply = Column(Integer, default=0)


class SourceItem(Base):
    __tablename__ = "source_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(Text, default="manual", index=True)
    url = Column(Text, default="")
    status = Column(Text, default="imported", index=True)
    title = Column(Text, default="")
    payload = Column(Text, default="{}")
    created_at = Column(Text, default=_now)
    updated_at = Column(Text, default=_now)


class Experience(Base):
    __tablename__ = "experiences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_job_id = Column(Text, index=True, default="")
    topic = Column(Text, default="")
    title = Column(Text, default="")
    insights = Column(Text, default="")
    metrics = Column(Text, default="{}")
    embedding = Column(Text, default="[]")
    score = Column(Float, default=0.0)
    created_at = Column(Text, default=_now)
    updated_at = Column(Text, default=_now)


def init_db() -> None:
    Base.metadata.create_all(engine)
    _migrate_jobs()
    _migrate_metrics()


def _migrate_jobs() -> None:
    import sqlalchemy as sa

    with engine.begin() as conn:
        cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(jobs)"))}
        adds = {
            "channel": 'TEXT DEFAULT "bilibili"',
            "target_platforms": 'TEXT DEFAULT \'["bilibili"]\'',
            "visual_style": 'TEXT DEFAULT "tech_infographic"',
            "generation_mode": 'TEXT DEFAULT "balanced"',
            "character_id": 'TEXT DEFAULT "host_default"',
            "review_status": 'TEXT DEFAULT "not_required"',
            "asset_pack_path": 'TEXT DEFAULT ""',
            "published": "INTEGER DEFAULT 0",
            "own_bvid": 'TEXT DEFAULT ""',
            "published_at": 'TEXT DEFAULT ""',
            "publish_records": 'TEXT DEFAULT "{}"',
        }
        for name, ddl in adds.items():
            if name not in cols:
                conn.execute(sa.text(f"ALTER TABLE jobs ADD COLUMN {name} {ddl}"))


def _migrate_metrics() -> None:
    import sqlalchemy as sa

    with engine.begin() as conn:
        cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(job_metrics)"))}
        if "platform" not in cols:
            conn.execute(sa.text('ALTER TABLE job_metrics ADD COLUMN platform TEXT DEFAULT "bilibili"'))


def create_job(job_id: str, source: str, style: str,
               channel: str = "bilibili",
               target_platforms: list[str] | None = None,
               visual_style: str = "tech_infographic",
               generation_mode: str = "balanced",
               character_id: str = "host_default",
               review_status: str = "pending") -> Job:
    init_db()
    with SessionLocal() as s:
        job = Job(
            id=job_id,
            source=source,
            style=style,
            channel=channel or "bilibili",
            target_platforms=json.dumps(target_platforms or ["bilibili"], ensure_ascii=False),
            visual_style=visual_style or "tech_infographic",
            generation_mode=generation_mode or "balanced",
            character_id=character_id or "host_default",
            review_status=review_status or "pending",
        )
        s.add(job)
        s.commit()
        s.refresh(job)
        return job


def update_job(job_id: str, **fields) -> None:
    with SessionLocal() as s:
        job = s.get(Job, job_id)
        if job is None:
            return
        for k, v in fields.items():
            if hasattr(job, k):
                if k in ("manual_review", "published"):
                    v = 1 if v else 0
                if k in ("target_platforms", "publish_records", "result") and not isinstance(v, str):
                    v = json.dumps(v, ensure_ascii=False)
                setattr(job, k, v)
        job.updated_at = _now()
        s.commit()


def mark_published(job_id: str, own_bvid: str, platform: str = "bilibili",
                   url: str = "") -> bool:
    with SessionLocal() as s:
        job = s.get(Job, job_id)
        if job is None:
            return False
        job.published = 1
        if platform == "bilibili":
            job.own_bvid = own_bvid
        job.status = "published"
        job.published_at = _now()
        records = json.loads(job.publish_records or "{}")
        records[platform] = {
            "external_id": own_bvid,
            "url": url or "",
            "published_at": _now(),
        }
        job.publish_records = json.dumps(records, ensure_ascii=False)
        job.updated_at = _now()
        s.commit()
        return True


def get_job(job_id: str) -> dict | None:
    with SessionLocal() as s:
        job = s.get(Job, job_id)
        if job is None:
            return None
        return _job_to_dict(job)


def list_jobs(limit: int = 30) -> list[dict]:
    init_db()
    with SessionLocal() as s:
        rows = s.query(Job).order_by(Job.created_at.desc()).limit(limit).all()
        return [_job_to_dict(j) for j in rows]


def list_published_jobs() -> list[dict]:
    init_db()
    with SessionLocal() as s:
        rows = s.query(Job).filter(Job.published == 1).all()
        return [_job_to_dict(j) for j in rows]


def _job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "source": job.source,
        "channel": job.channel or "bilibili",
        "target_platforms": json.loads(job.target_platforms or '["bilibili"]'),
        "visual_style": job.visual_style or "tech_infographic",
        "generation_mode": job.generation_mode or "balanced",
        "character_id": job.character_id or "host_default",
        "review_status": job.review_status or "not_required",
        "asset_pack_path": job.asset_pack_path or "",
        "status": job.status,
        "run_dir": job.run_dir,
        "title": job.title,
        "style": job.style,
        "manual_review": bool(job.manual_review),
        "error": job.error,
        "result": json.loads(job.result or "{}"),
        "published": bool(job.published),
        "own_bvid": job.own_bvid,
        "published_at": job.published_at,
        "publish_records": json.loads(job.publish_records or "{}"),
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def add_event(job_id: str, kind: str, message: str = "", payload: dict | None = None) -> int:
    with SessionLocal() as s:
        ev = JobEvent(job_id=job_id, kind=kind, message=message,
                      payload=json.dumps(payload or {}, ensure_ascii=False))
        s.add(ev)
        s.commit()
        return ev.id


def events_after(job_id: str, after_id: int = 0, limit: int = 1000) -> list[dict]:
    init_db()
    with SessionLocal() as s:
        rows = (s.query(JobEvent)
                .filter(JobEvent.job_id == job_id, JobEvent.id > after_id)
                .order_by(JobEvent.id.asc()).limit(limit).all())
        return [{
            "id": e.id,
            "kind": e.kind,
            "message": e.message,
            "payload": json.loads(e.payload or "{}"),
            "ts": e.ts,
        } for e in rows]


def record_metric(job_id: str, stat: dict, platform: str = "bilibili") -> dict:
    with SessionLocal() as s:
        row = JobMetric(
            job_id=job_id,
            platform=platform or "bilibili",
            view=int(stat.get("view", 0)),
            like=int(stat.get("like", 0)),
            coin=int(stat.get("coin", 0)),
            share=int(stat.get("share", 0)),
            favorite=int(stat.get("favorite", 0)),
            danmaku=int(stat.get("danmaku", 0)),
            reply=int(stat.get("reply", 0)),
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return {
            "id": row.id, "job_id": row.job_id, "captured_at": row.captured_at,
            "platform": row.platform,
            "view": row.view, "like": row.like, "coin": row.coin, "share": row.share,
            "favorite": row.favorite, "danmaku": row.danmaku, "reply": row.reply,
        }


def list_metrics(job_id: str, limit: int = 100) -> list[dict]:
    init_db()
    with SessionLocal() as s:
        rows = (s.query(JobMetric).filter(JobMetric.job_id == job_id)
                .order_by(JobMetric.id.desc()).limit(limit).all())
        return [{
            "id": r.id, "captured_at": r.captured_at, "platform": r.platform,
            "view": r.view, "like": r.like,
            "coin": r.coin, "share": r.share, "favorite": r.favorite,
            "danmaku": r.danmaku, "reply": r.reply,
        } for r in reversed(rows)]


def upsert_experience(source_job_id: str, topic: str, title: str, insights: str,
                      metrics: dict, embedding: list[float], score: float) -> int:
    with SessionLocal() as s:
        row = s.query(Experience).filter(Experience.source_job_id == source_job_id).first()
        if row is None:
            row = Experience(source_job_id=source_job_id)
            s.add(row)
        row.topic = topic
        row.title = title
        row.insights = insights
        row.metrics = json.dumps(metrics, ensure_ascii=False)
        row.embedding = json.dumps(embedding)
        row.score = float(score)
        row.updated_at = _now()
        s.commit()
        s.refresh(row)
        return row.id


def list_experiences(limit: int = 50) -> list[dict]:
    init_db()
    with SessionLocal() as s:
        rows = s.query(Experience).order_by(Experience.id.desc()).limit(limit).all()
        return [_exp_to_dict(r) for r in rows]


def load_embeddings() -> list[dict]:
    init_db()
    with SessionLocal() as s:
        rows = s.query(Experience).all()
        return [{
            "id": r.id,
            "source_job_id": r.source_job_id,
            "topic": r.topic,
            "title": r.title,
            "insights": r.insights,
            "metrics": json.loads(r.metrics or "{}"),
            "embedding": json.loads(r.embedding or "[]"),
        } for r in rows if r.embedding and r.embedding != "[]"]


def _exp_to_dict(row: Experience) -> dict:
    return {
        "id": row.id,
        "source_job_id": row.source_job_id,
        "topic": row.topic,
        "title": row.title,
        "insights": row.insights,
        "metrics": json.loads(row.metrics or "{}"),
        "score": row.score,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def upsert_source_item(platform: str, url: str, *,
                       status: str = "imported", title: str = "",
                       payload: dict | None = None) -> dict:
    init_db()
    with SessionLocal() as s:
        row = s.query(SourceItem).filter(
            SourceItem.platform == (platform or "manual"),
            SourceItem.url == (url or ""),
        ).first()
        if row is None:
            row = SourceItem(platform=platform or "manual", url=url or "")
            s.add(row)
        row.status = status or row.status
        row.title = title or row.title
        row.payload = json.dumps(payload or {}, ensure_ascii=False)
        row.updated_at = _now()
        s.commit()
        s.refresh(row)
        return {
            "id": row.id,
            "platform": row.platform,
            "url": row.url,
            "status": row.status,
            "title": row.title,
            "payload": json.loads(row.payload or "{}"),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }


def list_source_items(platform: str = "", status: str = "", limit: int = 100) -> list[dict]:
    init_db()
    with SessionLocal() as s:
        qs = s.query(SourceItem)
        if platform:
            qs = qs.filter(SourceItem.platform == platform)
        if status:
            qs = qs.filter(SourceItem.status == status)
        rows = qs.order_by(SourceItem.id.desc()).limit(max(1, min(limit, 500))).all()
        return [{
            "id": row.id,
            "platform": row.platform,
            "url": row.url,
            "status": row.status,
            "title": row.title,
            "payload": json.loads(row.payload or "{}"),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        } for row in rows]


init_db()
