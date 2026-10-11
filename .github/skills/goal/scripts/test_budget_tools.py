"""Offline regression tests; no network, credentials or production tracker writes."""
import contextlib
import io
import json
import tempfile
import unittest
import subprocess
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
    def test_markdown_cli_utf8_output(self):
        command = [sys.executable, "-B", str(Path(__file__).with_name("opencode_usage.py")), "--catalog", "--markdown"]
        result = subprocess.run(command, capture_output=True, encoding="utf-8", check=True)
        self.assertEqual(result.stdout.replace("\r\n", "\n"), b.markdown())

    def test_complete_catalog_and_nonuniform_plan_scaling(self):
        self.assertEqual(len(b.CATALOG),32)
        self.assertEqual(b.estimate("GLM-5.3","go-plus")["windows"]["monthly"]["usd"],120)
        self.assertEqual(b.estimate("GLM-5.2","go-plus")["windows"]["monthly"]["usd"],180)
        self.assertEqual(b.estimate("Kimi K3","go")["windows"]["rolling"]["usd"],3)

    def test_reproducible_cost_and_tokens(self):
        e=b.estimate("Kimi K3","go")
        self.assertAlmostEqual(e["cost_usd"],.072)
        self.assertEqual(e["windows"]["rolling"]["requests"],41)
        self.assertEqual(e["windows"]["rolling"]["tokens"],41*70000)

    def test_context_peak_and_cache_write_prices(self):
        self.assertEqual(b.prices("Claude Haiku 5.5",100000)[0],.1)
        self.assertEqual(b.prices("Claude Haiku 5.5",100001)[0],.5)
        self.assertAlmostEqual(b.estimate("DeepSeek V4 Pro","go")["cost_usd"],
            2*b.estimate("DeepSeek V4 Pro","go",off_peak=True)["cost_usd"])
        self.assertAlmostEqual(b.estimate("Qwen3.8 Max","go",(0,0,0,1000))["cost_usd"],.0025)

    def test_aliases_and_exclusion_across_providers(self):
        for name in ("Kimi K2.6 (Go) (opencode)","opencode-go/kimi-k2.7-code",
                     "Kimi K2.7 Code (opencodego)","Kimi K2.6 (openrouter)"):
            self.assertIn(b.canonical(name), b.EXCLUDED)
            self.assertIsNotNone(t.blocked(empty(),name))
        self.assertEqual(b.canonical("DeepSeek V4 Pro (New) (opencodego)"),"DeepSeek V4 Pro")

    def test_quality_then_efficiency_for_sustainable_batch(self):
        r=s.rank_models(healthy(),"go","builder",
            ["GLM-5.3 (opencodego)","GLM-5.2 (opencodego)","GLM-5.3-Flash (opencodego)"],
            empty(),target=50)
        self.assertEqual(r["selected"]["canonical"],"GLM-5.2")
        self.assertTrue(r["selected"]["fits_target"])

    def test_pressure_changes_choice_before_exhaustion(self):
        names=["GLM-5.2 (opencodego)","GLM-5.3-Flash (opencodego)"]
        low=s.rank_models(healthy(),"go","builder",names,empty(),target=50)
        high=s.rank_models(healthy(75),"go","builder",names,empty(),target=50)
        self.assertEqual(low["selected"]["canonical"],"GLM-5.2")
        self.assertEqual(high["selected"]["canonical"],"GLM-5.3-Flash")

    def test_weekly_and_monthly_constrain_selection(self):
        for window in ("weekly","monthly"):
            usage=healthy(); usage[window]["percent"]=90
            r=s.rank_models(usage,"go","builder",["GLM-5.2 (opencodego)"],empty())
            self.assertIsNone(r["selected"])

    def test_kimi3_eligible_but_excluded_versions_never_selected(self):
        r=s.rank_models(healthy(),"go","inspector",
            ["Kimi K2.6 (opencodego)","Kimi K2.7 Code (opencodego)","Kimi K3 (opencodego)"],
            empty(),builder="GLM-5.2",target=10)
        self.assertEqual(r["selected"]["canonical"],"Kimi K3")
        self.assertEqual(len(r["rejected"]),2)

    def test_independent_inspector_family(self):
        r=s.rank_models(healthy(),"go","inspector",["GLM-5.3 (opencodego)","Hy4 preview (opencodego)"],
            empty(),builder="GLM-5.2")
        self.assertEqual(r["selected"]["canonical"],"Hy4 preview")
        self.assertEqual(r["rejected"][0]["reason"],"same family as Builder")

    def test_training_requires_opt_in(self):
        labels=["Muse Spark 1.3 Contributor (opencodego)"]
        self.assertIsNone(s.rank_models(healthy(),"go","builder",labels,empty())["selected"])
        self.assertIsNotNone(s.rank_models(healthy(),"go","builder",labels,empty(),allow_training=True)["selected"])

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
        r=s.rank_models(usage,"go","builder",labels,empty(),allow_free=True,allow_openrouter=True)
        self.assertEqual(r["selected"]["provider"],"free")

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
            source.write_text('---\nname: Builder\nmodel: Old\nuser-invocable: false\n---\nPreserved instructions.\n')
            r=s.prepare_agent(source,dest,"GLM-5.2 (opencodego)","builder","goal")
            self.assertIn('model: "GLM-5.2 (opencodego)"',dest.read_text())
            self.assertIn("Preserved instructions.",dest.read_text())
            self.assertEqual(r["agent_name"],"Budget goal: Builder")
            self.assertIsNone(r["actual_model"])
            with self.assertRaises(ValueError): s.prepare_agent(source,dest,"Kimi K2.6 (openrouter)","builder","goal")

    def test_prepare_preserves_unrelated_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source.md"; dest=Path(directory)/"generated.md"
            source.write_text('---\nname: Builder\nmodel: Old\n---\nBody')
            dest.write_text("user owned")
            with self.assertRaises(ValueError): s.prepare_agent(source,dest,"GLM-5.2","builder","goal")
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
