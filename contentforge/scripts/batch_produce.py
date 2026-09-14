import json
import sys
import time
from datetime import datetime

from forge.graph import new_job, run_job_graph
from forge.store import get_job

LOG = open("_batch.log", "w", encoding="utf-8")


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.write(line + "\n")
    LOG.flush()


def main() -> None:
    bvids = sys.argv[1:] or [
        "BV1BtZJYBE4G",
        "BV17TZEYPEug",
        "BV1w6ZEYrEsb",
    ]
    results = []
    for bv in bvids:
        job_id = new_job(bv, "")
        log(f"START {bv} job={job_id}")
        t0 = time.time()
        try:
            run_job_graph(job_id, bv)
            job = get_job(job_id)
            cost = int(time.time() - t0)
            ok = job.get("status") == "done"
            results.append({"bvid": bv, "job_id": job_id, "ok": ok,
                            "status": job.get("status"), "sec": cost})
            log(f"DONE  {bv} job={job_id} status={job.get('status')} sec={cost}")
            if not ok:
                log(f"  error={job.get('error', '')[:200]}")
        except Exception as e:
            results.append({"bvid": bv, "job_id": job_id, "ok": False,
                            "status": "exception", "sec": int(time.time() - t0)})
            log(f"FAIL  {bv} job={job_id} exc={str(e)[:200]}")

    log("SUMMARY " + json.dumps(results, ensure_ascii=False))
    LOG.close()


if __name__ == "__main__":
    main()
