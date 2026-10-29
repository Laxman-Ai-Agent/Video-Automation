"""The `final` review is shown the LLM reviews of the stages before it: only stages that need a review, and a review made for other inputs is said to be stale.
Found 2026-10-30: `llm_review_timeline.json` (2026-10-27, from a 7-scene timeline, a stage that has no review any more) made the final review ask for data about "7 scenes" of an 8-scene video.
Run: python -m pytest tests/test_final_upstream_reviews.py -q"""
from SYSTEM.policies import llm_review


def _save(pdir, stage, status, fresh=True):
    llm_review.save_review(pdir, stage, "16:9", {"schema": llm_review.SCHEMA, "version": 1, "stage": stage, "aspect": "16:9", "status": status, "score": 0.9, "summary": f"{stage} summary", "findings": [],
                                                  "input_fingerprint": llm_review.compute_stage_input_fingerprint(pdir, stage, "16:9") if fresh else "other",
                                                  "output_fingerprint": llm_review.compute_stage_output_fingerprint(pdir, stage, "16:9"), "reviewed_at": 0})


def test_only_current_reviews_of_stages_that_need_one_are_shown_to_the_final_review(tmp_path):
    _save(tmp_path, "timeline", "needs_review")                       # a leftover: the timeline is decided by its own checks
    _save(tmp_path, "qc", "passed")
    _save(tmp_path, "approval", "passed", fresh=False)                # made for other inputs
    shown = {r["stage"]: r for r in llm_review.build_stage_payload(tmp_path, "final")["upstream_stage_reviews"]}
    assert "timeline" not in shown
    assert shown["qc"]["status"] == "passed" and shown["qc"]["score"] == 0.9
    assert shown["approval"]["status"] == "stale" and shown["approval"]["score"] is None and "other inputs" in shown["approval"]["summary"]
