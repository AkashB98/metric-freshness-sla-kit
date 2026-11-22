"""Served-answer cache with backfill invalidation.

An answer is cached together with the fingerprint of the partition it
was computed from (partition_id + content_hash + definition version).
When a backfill rewrites that partition - same id, new content hash -
the cached answer no longer describes the data, so re-serving it is
refused with reason BACKFILL_INVALIDATED until it is recomputed.
"""
from __future__ import annotations
from models import Verdict

class AnswerCache:
    def __init__(self):
        self._entries = {}  # (metric, partition_id) -> dict

    @staticmethod
    def _fingerprint(part):
        return (part.partition_id, part.content_hash, part.definition_version)

    def store(self, part, verdict):
        if verdict.decision != "SERVE":
            raise ValueError("only SERVE verdicts may be cached")
        self._entries[(part.metric, part.partition_id)] = {
            "fingerprint": self._fingerprint(part), "value": verdict.value}

    def reservice_check(self, part) -> Verdict:
        """May the cached answer for this partition still be served?"""
        entry = self._entries.get((part.metric, part.partition_id))
        if entry is None:
            return Verdict(part.metric, part.partition_id, "REFUSE",
                           ["NOT_CACHED"], "no cached answer for this partition", None)
        if entry["fingerprint"] != self._fingerprint(part):
            return Verdict(part.metric, part.partition_id, "REFUSE",
                           ["BACKFILL_INVALIDATED"],
                           "partition was rewritten after the answer was cached (backfill); cached value must not be re-served", None)
        return Verdict(part.metric, part.partition_id, "SERVE", [],
                       "cached answer still matches partition fingerprint", entry["value"])

    def invalidate(self, metric, partition_id):
        self._entries.pop((metric, partition_id), None)

    def __len__(self): return len(self._entries)
