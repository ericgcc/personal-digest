"""Offline regression tests; no network, credentials or production tracker writes."""
import contextlib
import io
import json
import tempfile
import unittest
import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import budget_models as b
import model_tracker as t
import opencode_usage as u
import select_model as s


def healthy(percent=0):
    return {w: {"status":"ok","percent":percent,"resetsAt":(t.now()+timedelta(days=1)).isoformat()} for w in b.WINDOWS}


def empty():
    return {"version":2,"models":{},"accounts":{}}


class BudgetTests(unittest.TestCase):
    def test_profile_estimate_is_the_only_cost_source(self):
        labels=["DeepSeek V4.1 Flash (opencodego)","GLM-5.2 (opencodego)"]
        result=s.rank_models(healthy(),"go","builder",labels,empty(),expected_requests=200)
        self.assertEqual(result["selected"]["canonical"],"DeepSeek V4.1 Flash")
        self.assertEqual(result["selected"]["usd_per_request"],
            b.estimate("DeepSeek V4.1 Flash","go",b.CONSERVATIVE_PROFILE)["cost_usd"])
        self.assertEqual([m["canonical"] for m in result["ranked"]],
            ["DeepSeek V4.1 Flash"])
        for item in result["ranked"]:
            self.assertNotIn("cost_source",item)
            self.assertNotIn("observed_requests",item)

    def test_builder_reserves_inspector_capacity_but_inspector_can_use_it(self):
        usage=healthy(85)
        labels=["Hy4 preview (opencodego)"]
        builder=s.rank_models(usage,"go","builder",labels,empty(),expected_requests=1)
        inspector=s.rank_models(usage,"go","inspector",labels,empty(),builder="GLM-5.2",expected_requests=1)
        self.assertIsNone(builder["selected"])
        self.assertIsNotNone(inspector["selected"])
        self.assertEqual(builder["reserve_pp"],15.0)
        self.assertEqual(inspector["reserve_pp"],2.0)

    def test_no_selection_when_no_model_can_finish_batch(self):
        result=s.rank_models(healthy(),"go","builder",["GLM-5.2 (opencodego)"],empty(),expected_requests=10000)
        self.assertIsNone(result["selected"])
        self.assertEqual(result["rejected"][0]["reason"],"planned batch exceeds reserved allowance in a window")

    def test_single_request_default_and_check_scope(self):
        result=s.rank_models(healthy(),"go","builder",["GLM-5.2 (opencodego)"],empty())
        self.assertEqual(result["expected_requests"],1)
        self.assertEqual(result["check_scope"],"single-request feasibility estimate")
        batch=s.rank_models(healthy(),"go","builder",["GLM-5.2 (opencodego)"],empty(),expected_requests=50)
        self.assertEqual(batch["check_scope"],"estimated multi-request batch")
        with self.assertRaises(ValueError):
            s.rank_models(healthy(),"go","builder",["GLM-5.2 (opencodego)"],empty(),expected_requests=0)

    def test_normal_pressure_keeps_precedence_order(self):
        # Conservative default profile: only GLM-5.3-Flash fits 50 requests in
        # the Go 5h window, so it leads despite lower precedence position.
        names=["GLM-5.2 (opencodego)","DeepSeek V4 Pro (opencodego)","GLM-5.3-Flash (opencodego)"]
        r=s.rank_models(healthy(),"go","builder",names,empty(),expected_requests=50)
        self.assertEqual(r["selection_mode"],"normal")
        self.assertEqual(r["selected"]["canonical"],"GLM-5.3-Flash")
        self.assertIn("first eligible model in Builder precedence",r["selection_reason"])
        # With a single-request estimate the full precedence order applies.
        r1=s.rank_models(healthy(),"go","builder",names,empty())
        self.assertEqual(r1["selected"]["canonical"],"DeepSeek V4 Pro")

    def test_high_pressure_conserve_reranks_within_quality_floor(self):
        # DeepSeek V4 Pro (q5, expensive) vs GLM-5.3-Flash (q4, cheap): under
        # rolling pressure >= 50 the cheaper q4 model leads within the floor.
        names=["DeepSeek V4 Pro (opencodego)","GLM-5.3-Flash (opencodego)"]
        r=s.rank_models(healthy(55),"go","builder",names,empty(),expected_requests=50)
        self.assertEqual(r["selection_mode"],"conserve")
        self.assertEqual(r["selected"]["canonical"],"GLM-5.3-Flash")
        self.assertIn("lower projected 5-hour",r["selection_reason"])
        # Quality floor: a model two tiers below the strongest feasible is deferred.
        self.assertEqual(r["ranked"][0]["quality"],4)

    def test_no_candidate_reason(self):
        r=s.rank_models(healthy(),"go","builder",["GLM-5.2 (opencodego)"],empty(),expected_requests=10000)
        self.assertIsNone(r["selected"])
        self.assertEqual(r["selection_reason"],"No eligible model fits the current budget and quality requirements.")
        self.assertEqual(r["usage_percent"],{w:0 for w in b.WINDOWS})

    def test_aliases_and_exclusion_across_providers(self):
        for name in ("Kimi K2.6 (Go) (opencode)","opencode-go/kimi-k2.7-code",
                     "Kimi K2.7 Code (opencodego)","Kimi K2.6 (openrouter)"):
            self.assertIn(b.canonical(name), b.EXCLUDED)
            self.assertIsNotNone(t.blocked(empty(),name))
        self.assertEqual(b.canonical("DeepSeek V4 Pro (New) (opencodego)"),"DeepSeek V4 Pro")

    def test_precedence_order_and_dynamic_rerank(self):
        names=["GLM-5.2 (opencodego)","GLM-5.3-Flash (opencodego)","DeepSeek V4 Pro (opencodego)"]
        r=s.rank_models(healthy(),"go","builder",names,empty(),expected_requests=5)
        self.assertEqual(r["selected"]["canonical"],"DeepSeek V4 Pro")
        self.assertEqual([m["canonical"] for m in r["ranked"]],
            ["DeepSeek V4 Pro","GLM-5.3-Flash","GLM-5.2"])

    def test_pressure_changes_choice_before_exhaustion(self):
        names=["DeepSeek V4 Pro (opencodego)","GLM-5.3-Flash (opencodego)"]
        low=s.rank_models(healthy(),"go","builder",names,empty(),expected_requests=5)
        high=s.rank_models(healthy(75),"go","builder",names,empty(),expected_requests=5)
        self.assertEqual(low["selected"]["canonical"],"DeepSeek V4 Pro")
        self.assertEqual(high["selected"]["canonical"],"GLM-5.3-Flash")

    def test_models_outside_precedence_rejected(self):
        r=s.rank_models(healthy(),"go","builder",["GLM-5.3 (opencodego)"],empty(),expected_requests=50)
        self.assertIsNone(r["selected"])
        self.assertEqual(r["rejected"][0]["reason"],"outside curated role precedence")

    def test_premium_requires_explicit_opt_in_and_goes_first(self):
        names=["GLM-5.3-Flash (opencodego)","GLM-5.3 (opencodego)"]
        base=s.rank_models(healthy(),"go","builder",names,empty(),expected_requests=5)
        self.assertEqual(base["selected"]["canonical"],"GLM-5.3-Flash")
        r=s.rank_models(healthy(),"go","builder",names,empty(),expected_requests=5,allow_premium=True)
        self.assertEqual(r["selected"]["canonical"],"GLM-5.3")

    def test_inspector_default_min_quality_four_blocks_hy3(self):
        r=s.rank_models(healthy(),"go","inspector",["Hy3 (opencodego)"],empty(),builder="GLM-5.2")
        self.assertIsNone(r["selected"])
        self.assertEqual(r["rejected"][0]["reason"],"below required subjective quality tier")
        self.assertIsNotNone(s.rank_models(healthy(),"go","inspector",["Hy3 (opencodego)"],
            empty(),builder="GLM-5.2",min_quality=3)["selected"])

    def test_weekly_and_monthly_constrain_selection(self):
        for window in ("weekly","monthly"):
            usage=healthy(); usage[window]["percent"]=90
            r=s.rank_models(usage,"go","builder",["GLM-5.2 (opencodego)"],empty())
            self.assertIsNone(r["selected"])

    def test_kimi3_eligible_but_excluded_versions_never_selected(self):
        r=s.rank_models(healthy(),"go","inspector",
            ["Kimi K2.6 (opencodego)","Kimi K2.7 Code (opencodego)","Kimi K3 (opencodego)"],
            empty(),builder="GLM-5.2",expected_requests=10)
        self.assertEqual(r["selected"]["canonical"],"Kimi K3")
        self.assertEqual(len(r["rejected"]),2)

    def test_independent_inspector_family(self):
        r=s.rank_models(healthy(),"go","inspector",["Kimi K3 (opencodego)","Hy4 preview (opencodego)"],
            empty(),builder="Kimi K2.7 Code")
        self.assertEqual(r["selected"]["canonical"],"Hy4 preview")
        self.assertEqual(r["rejected"][0]["reason"],"same family as Builder")

    def test_inspector_only_mode_without_builder(self):
        r=s.rank_models(healthy(),"go","inspector",["Hy4 preview (opencodego)"],empty(),builder="none")
        self.assertIsNotNone(r["selected"])
        self.assertEqual(r["family_independence"],"unverified: no Builder")

    def test_no_independent_inspector_means_no_selection(self):
        # Only same-family candidates available: no selection rather than violation.
        r=s.rank_models(healthy(),"go","inspector",["Kimi K3 (opencodego)"],empty(),builder="Kimi K2.7 Code")
        self.assertIsNone(r["selected"])
        self.assertEqual(r["rejected"][0]["reason"],"same family as Builder")

    def test_openrouter_inspector_skips_builder_family_and_keeps_declared_order(self):
        # GLM-5.3-Flash (glm) is first in OPENROUTER_INSPECTOR_PRECEDENCE but shares
        # the Builder's family; DeepSeek V4.1 Flash (deepseek) is independent.
        # Both are Inspector quality 3, so an explicit lowered minimum is required.
        labels=["Z.ai: GLM 5.3 Flash (openrouter)","DeepSeek: DeepSeek V4.1 Flash (openrouter)"]
        r=s.rank_models(healthy(),"go","inspector",labels,empty(),builder="GLM-5.2",
            allow_openrouter=True,min_quality=3)
        self.assertEqual(r["selected"]["canonical"],"DeepSeek V4.1 Flash")
        self.assertEqual(r["rejected"][0]["reason"],"same family as Builder")
        # With no family conflict, declared order wins (GLM-5.3-Flash first).
        r2=s.rank_models(healthy(),"go","inspector",labels,empty(),builder="DeepSeek V4 Pro",
            allow_openrouter=True,min_quality=3)
        self.assertEqual(r2["selected"]["canonical"],"GLM-5.3-Flash")

    def test_tracker_block_removes_candidate_from_selection(self):
        # A model-specific failure recorded in the tracker must prevent the
        # selector from choosing that model again, even with healthy usage.
        labels=["DeepSeek V4 Pro (opencodego)","GLM-5.2 (opencodego)"]
        base=s.rank_models(healthy(),"go","builder",labels,empty())
        self.assertEqual(base["selected"]["canonical"],"DeepSeek V4 Pro")
        data=empty()
        data["models"][t.model_key("DeepSeek V4 Pro (opencodego)")]=t.make_record("unknown")
        r=s.rank_models(healthy(),"go","builder",labels,data)
        self.assertEqual(r["selected"]["canonical"],"GLM-5.2")
        self.assertEqual(r["rejected"][0]["reason"],"tracker block")

    def test_openrouter_respects_quality_minimum(self):
        # GLM-5.3-Flash (Inspector quality 3) must not serve as an Inspector
        # fallback when the default minimum is 4; DeepSeek V4.1 Flash (3) also
        # fails, so no external selection is returned. The family check runs
        # first for the GLM label (same family as the GLM Builder).
        labels=["Z.ai: GLM 5.3 Flash (openrouter)","DeepSeek: DeepSeek V4.1 Flash (openrouter)"]
        r=s.rank_models(healthy(),"go","inspector",labels,empty(),builder="GLM-5.2",allow_openrouter=True)
        self.assertIsNone(r["selected"])
        reasons={x["model"]:x["reason"] for x in r["rejected"]}
        self.assertEqual(reasons[labels[0]],"same family as Builder")
        self.assertEqual(reasons[labels[1]],"below required subjective quality tier")
        # An explicit lower minimum permits the independent fallback; the GLM
        # label still loses to the family check against the GLM Builder.
        r2=s.rank_models(healthy(),"go","inspector",labels,empty(),builder="DeepSeek V4 Pro",
            allow_openrouter=True,min_quality=3)
        self.assertEqual(r2["selected"]["canonical"],"GLM-5.3-Flash")

    def test_free_models_blocked_by_explicit_high_min_quality(self):
        # --min-quality 4|5 must prevent the documented free-model downgrade.
        # LongCat is quality 2, so even the low-quality authorization needs an
        # explicit lowered minimum.
        labels=["LongCat 2.5 Preview Free (opencodego)"]
        usage=healthy(100)
        self.assertIsNotNone(s.rank_models(usage,"go","builder",labels,empty(),
            allow_free=True,allow_low_quality_free=True,min_quality=2)["selected"])
        self.assertIsNone(s.rank_models(usage,"go","builder",labels,empty(),
            allow_free=True,allow_low_quality_free=True,min_quality=4)["selected"])

    def test_cli_free_fallback_and_conservative_default_profile(self):
        # CLI-level: the documented free-model fallback works end to end, and
        # the runtime default profile assumes zero cache reads.
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            snap=root/"usage.json"; avail=root/"models.json"
            usage=healthy(100); usage["rolling"].update(status="rate-limited",percent=100)
            snap.write_text(json.dumps({"timestamp":t.now().isoformat(),"plan":"go","usage":usage}))
            avail.write_text(json.dumps(["LongCat 2.5 Preview Free (opencodego)"]))
            out=io.StringIO()
            with contextlib.redirect_stdout(out):
                code=s.main(["--plan","go","--role","builder","--available",str(avail),
                    "--usage-file",str(snap),"--tracker",str(root/"tracker.json"),
                    "--allow-free","--allow-low-quality-free","--min-quality","2"])
            result=json.loads(out.getvalue())
            self.assertEqual(code,0)
            self.assertEqual(result["selected"]["provider"],"free")
            self.assertEqual(result["profile"],list(b.CONSERVATIVE_PROFILE))
            # Without both free flags, --min-quality 2 is refused (exit 3).
            out2=io.StringIO(); err2=io.StringIO()
            with contextlib.redirect_stdout(out2), contextlib.redirect_stderr(err2):
                code2=s.main(["--plan","go","--role","builder","--available",str(avail),
                    "--usage-file",str(snap),"--tracker",str(root/"tracker2.json"),
                    "--min-quality","2"])
            self.assertEqual(code2,3)
            # The default Builder minimum (3) cannot select quality-2 free models.
            out3=io.StringIO()
            with contextlib.redirect_stdout(out3):
                code3=s.main(["--plan","go","--role","builder","--available",str(avail),
                    "--usage-file",str(snap),"--tracker",str(root/"tracker3.json"),
                    "--allow-free","--allow-low-quality-free"])
            self.assertEqual(code3,2)
            self.assertIsNone(json.loads(out3.getvalue())["selected"])

    def test_openrouter_requires_explicit_authorization(self):
        labels=["Z.ai: GLM 5.3 Flash (openrouter)","GLM-5.2 (opencodego)"]
        r=s.rank_models(healthy(),"go","builder",labels,empty())
        self.assertEqual(r["selected"]["provider"],"go")
        self.assertEqual(r["rejected"][0]["reason"],"outside curated OpenRouter precedence or --allow-openrouter not set")

    def test_paid_go_exhaustion_does_not_block_openrouter_or_free(self):
        labels=["Z.ai: GLM 5.3 Flash (openrouter)","LongCat 2.5 Preview Free (opencodego)","GLM-5.2 (opencodego)"]
        usage=healthy(); usage["rolling"].update(status="rate-limited",percent=100)
        data=empty(); t.sync_usage(data,usage)
        r=s.rank_models(usage,"go","builder",labels,data,allow_free=True,
            allow_low_quality_free=True,allow_openrouter=True,min_quality=2)
        # The paid-Go candidate is rejected through the tracker's account-wide
        # block; free and OpenRouter remain selectable.
        self.assertEqual(r["rejected"][0]["reason"],"tracker block")
        self.assertEqual(r["selected"]["provider"],"free")

    def test_training_requires_opt_in(self):
        labels=["Muse Spark 1.3 Contributor (opencodego)"]
        self.assertIsNone(s.rank_models(healthy(),"go","builder",labels,empty())["selected"])
        # Muse Contributor models are outside curated precedence regardless of consent.
        r=s.rank_models(healthy(),"go","builder",labels,empty(),allow_training=True)
        self.assertIsNone(r["selected"])
        self.assertEqual(r["rejected"][0]["reason"],"outside curated role precedence")

    def test_openrouter_last_and_paid_go_block_does_not_block_it(self):
        labels=["Z.ai: GLM 5.3 Flash (openrouter)","GLM-5.2 (opencodego)"]
        self.assertEqual(s.rank_models(healthy(),"go","builder",labels,empty(),allow_openrouter=True)["selected"]["provider"],"go")
        usage=healthy(); usage["rolling"].update(status="rate-limited",percent=100)
        data=empty(); t.sync_usage(data,usage)
        self.assertIsNone(t.blocked(data,labels[0]))
        self.assertEqual(s.rank_models(usage,"go","builder",labels,data,allow_openrouter=True)["selected"]["provider"],"openrouter")

    def test_free_before_openrouter(self):
        usage=healthy(100)
        labels=["LongCat 2.5 Preview Free (opencodego)","Z.ai: GLM 5.3 Flash (openrouter)"]
        r=s.rank_models(usage,"go","builder",labels,empty(),allow_free=True,
            allow_low_quality_free=True,allow_openrouter=True,min_quality=2)
        self.assertEqual(r["selected"]["provider"],"free")

    def test_free_models_never_select_for_inspector_or_without_low_quality_consent(self):
        labels=["LongCat 2.5 Preview Free (opencodego)"]
        self.assertIsNone(s.rank_models(healthy(100),"go","builder",labels,empty(),allow_free=True)["selected"])
        self.assertIsNone(s.rank_models(healthy(100),"go","inspector",labels,empty(),
            builder="GLM-5.2",allow_free=True,allow_low_quality_free=True)["selected"])

    def test_unknown_usage_cannot_select(self):
        with self.assertRaises(ValueError):
            s.rank_models({},"go","builder",["GLM-5.2"],empty())
        self.assertIn("unknown",u.advise({}))

    def test_invalid_percentage_rejected(self):
        for bad in (None, "20", True, float("nan"), -1, 101):
            usage=healthy(); usage["weekly"]["percent"]=bad
            with self.assertRaises(ValueError): u.validate_usage({"usage":usage})

    def test_all_windows_retained_until_each_reset(self):
        usage=healthy()
        usage["rolling"].update(status="rate-limited",percent=100,resetsAt=(t.now()+timedelta(hours=1)).isoformat())
        usage["monthly"].update(status="rate-limited",percent=100,resetsAt=(t.now()+timedelta(days=4)).isoformat())
        data=empty(); t.sync_usage(data,usage)
        t.prune(data,t.now()+timedelta(hours=2))
        self.assertNotIn("rolling",data["accounts"])
        self.assertIn("monthly",data["accounts"])
        self.assertIsNotNone(t.blocked(data,"GLM-5.2",t.now()+timedelta(hours=2)))

    def test_unknown_reset_recheck_expires(self):
        at=t.now()
        for value in (None, "invalid", "2026-10-10T10:00:00"):
            record=t.make_record("rolling",value,at=at)
            self.assertTrue(t.live(record,at))
            self.assertFalse(t.live(record,at+timedelta(minutes=6)))

    def test_legacy_null_and_computed_records_migrate(self):
        old=(t.now()-timedelta(days=3)).isoformat()
        for source in ("usage-api","computed-upper-bound"):
            data=t.migrate({"models":{},"account":{"window":"monthly","reset_at":None,
                "exhausted_at":old,"reset_source":source}})
            t.prune(data)
            self.assertFalse(data["accounts"])

    def test_refresh_clears_healthy_only(self):
        data=empty()
        data["models"]["go:GLM-5.2"]=t.make_record("unknown")
        for w in b.WINDOWS: data["accounts"][w]=t.make_record(w)
        usage=healthy(); usage["weekly"].update(status="rate-limited",percent=100)
        t.sync_usage(data,usage)
        self.assertEqual(set(data["accounts"]),{"weekly"})
        self.assertTrue(data["models"])

    def test_model_block_does_not_cross_provider(self):
        data=empty(); data["models"][t.model_key("GLM-5.3-Flash (opencodego)")]=t.make_record("unknown")
        self.assertIsNotNone(t.blocked(data,"GLM-5.3-Flash (Go) (opencode)"))
        self.assertIsNone(t.blocked(data,"Z.ai: GLM 5.3 Flash (openrouter)"))

    def test_corrupt_tracker_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"tracker.json"; path.write_text("{broken",encoding="utf-8")
            with self.assertRaises(ValueError): t.load_tracker(path)
            self.assertEqual(path.read_text(),"{broken")

    def test_timestamp_required_and_stale_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"snapshot.json"
            for stamp in (None,(t.now()-timedelta(hours=1)).isoformat()):
                path.write_text(json.dumps({"usage":healthy(),"timestamp":stamp}))
                with self.assertRaises(ValueError): u.snapshot_from_file(path)

    def test_prepare_binds_exact_selected_model(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source.md"; dest=Path(directory)/"generated.md"
            source.write_text('---\nname: Builder\nmodel: ""\nuser-invocable: false\n---\nPreserved instructions.\n')
            r=s.prepare_agent(source,dest,"GLM-5.2 (opencodego)","builder","goal")
            self.assertIn('model: "GLM-5.2 (opencodego)"',dest.read_text())
            self.assertIn("Preserved instructions.",dest.read_text())
            self.assertEqual(r["agent_name"],"Budget goal: Builder")
            self.assertIsNone(r["actual_model"])
            with self.assertRaises(ValueError): s.prepare_agent(source,dest,"Kimi K2.6 (openrouter)","builder","goal")

    def test_prepare_rejects_bare_catalog_name(self):
        """A bare catalog name cannot be resolved by the host and would silently
        fall back to the session default; preparation must refuse it."""
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source.md"; dest=Path(directory)/"generated.md"
            source.write_text('---\nname: Builder\nmodel: ""\n---\nBody')
            with self.assertRaises(ValueError): s.prepare_agent(source,dest,"GLM-5.2","builder","goal")

    def test_prepare_empty_label_resets_to_host_default(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source.md"; dest=Path(directory)/"generated.md"
            source.write_text('---\nname: Builder\nmodel: "GLM-5.2 (opencodego)"\n---\nBody')
            s.prepare_agent(source,dest,"","builder","goal")
            self.assertIn('model: ""',dest.read_text())
            self.assertIn("the host default model",dest.read_text())

    def test_prepare_overwrites_persistent_agent(self):
        """The role agent is persistent: a later selection overwrites the earlier
        binding in place, never creating a second file."""
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source.md"; dest=Path(directory)/"generated.md"
            source.write_text('---\nname: Builder\nmodel: ""\n---\nBody')
            s.prepare_agent(source,dest,"GLM-5.2 (opencodego)","builder","goal")
            s.prepare_agent(source,dest,"DeepSeek V4 Pro (New) (Go) (opencode)","builder","goal")
            self.assertIn('model: "DeepSeek V4 Pro (New) (Go) (opencode)"',dest.read_text())
            self.assertNotIn("GLM-5.2",dest.read_text())

    def test_prepare_preserves_unrelated_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source.md"; dest=Path(directory)/"generated.md"
            source.write_text('---\nname: Builder\nmodel: ""\n---\nBody')
            dest.write_text("user owned")
            with self.assertRaises(ValueError): s.prepare_agent(source,dest,"GLM-5.2 (opencodego)","builder","goal")
            self.assertEqual(dest.read_text(),"user owned")

    def test_gauge_json_and_record_handles_missing_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"tracker.json"
            usage=healthy(); usage["rolling"].update(status="rate-limited",percent=100,resetsAt=None)
            stream=io.StringIO()
            with patch.object(u,"load_api_key",return_value="test"), patch.object(u,"fetch_usage",return_value={"usage":usage}), contextlib.redirect_stdout(stream):
                result=u.main(["--json","--record","--tracker",str(path)])
            self.assertEqual(result,2)
            self.assertEqual(json.loads(stream.getvalue())["usage"],usage)
            data=t.load_tracker(path)
            self.assertFalse(t.live(data["accounts"]["rolling"],t.now()+timedelta(minutes=6)))

    def test_selector_cli_offline_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); snap=root/"usage.json"; available=root/"models.json"
            snap.write_text(json.dumps({"timestamp":t.now().isoformat(),"plan":"go-plus","usage":healthy()}))
            available.write_text(json.dumps(["Kimi K2.7 Code (opencodego)","GLM-5.2 (opencodego)"]))
            out=io.StringIO()
            with contextlib.redirect_stdout(out):
                result=s.main(["--plan","go-plus","--role","builder","--available",str(available),"--usage-file",str(snap),"--tracker",str(root/"tracker.json")])
            self.assertEqual(result,0)
            self.assertEqual(json.loads(out.getvalue())["selected"]["canonical"],"GLM-5.2")


if __name__ == "__main__":
    unittest.main()
