import argparse

from forge.graph import new_job, run_job_graph
from forge.store import get_job


def main():
    parser = argparse.ArgumentParser(description="同步跑一个 LangGraph 生产任务（测试用）")
    parser.add_argument("--bvid", required=True, help="B站 BVID 或链接")
    parser.add_argument("--style", default="", help="语言风格要求")
    args = parser.parse_args()

    job_id = new_job(args.bvid, args.style)
    print("job_id=%s start=%s" % (job_id, args.bvid))
    run_job_graph(job_id, args.bvid, args.style)
    job = get_job(job_id)
    print("job_id=%s status=%s title=%s run_dir=%s" % (
        job_id, job.get("status"), (job.get("title") or "")[:30], job.get("run_dir")))


if __name__ == "__main__":
    main()
