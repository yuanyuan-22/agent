import time

from forge.channels.bilibili import BiliClient

bv = "BV1vqhw6yEtT"
c = BiliClient()
t0 = time.time()
info = c.view(bv)
print("view ok %.1fs cid=%s title=%s" % (time.time() - t0, info.get("cid"), (info.get("title") or "")[:30]))
cid = int(info.get("cid") or 0)

t1 = time.time()
subs = c.subtitle_list(bv, cid)
print("subtitle_list %.1fs count=%s" % (time.time() - t1, len(subs)))

t2 = time.time()
cands = c.audio_candidates(bv, cid)
print("audio_candidates %.1fs n=%s first=%s" % (time.time() - t2, len(cands), ("mcdn" in cands[0]) if cands else None))

t3 = time.time()
wav = c.download_audio(bv, cid, "data/transcripts", cap_seconds=120)
import os
print("download_audio ok %.1fs size=%s" % (time.time() - t3, os.path.getsize(wav)))
c.close()
