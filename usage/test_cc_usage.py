"""Tests for cc-usage on synthetic transcripts. Run: python3 -m unittest usage/test_cc_usage.py"""
import contextlib, io, json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cc_usage  # noqa: E402

SID = "11111111-aaaa-bbbb-cccc-000000000001"


def usage(inp=0, out=0, cr=0, w5=0, w1=0, **extra):
    u = {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cr,
         "cache_creation_input_tokens": w5 + w1,
         "cache_creation": {"ephemeral_5m_input_tokens": w5, "ephemeral_1h_input_tokens": w1}}
    u.update(extra)
    return u


def line(ts, model="claude-opus-5-5", u=None, req="r1", agent=None, effort="high", tools=0, **top):
    d = {"type": "assistant", "timestamp": ts, "requestId": req, "sessionId": SID, "cwd": "/work/proj",
         "version": "2.1.330", "effort": effort, "isSidechain": agent is not None,
         "message": {"id": "msg_" + req, "model": model, "usage": u,
                     "content": [{"type": "tool_use", "id": "t%d" % i} for i in range(tools)]}}
    if agent:
        d["agentId"] = agent
    d.update(top)
    return d


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.cfg = os.path.join(t, "cfg")
        self.proj = os.path.join(self.cfg, "projects", "-work-proj")
        os.makedirs(self.proj)
        self.env = {"CLAUDE_CONFIG_DIR": self.cfg, "CC_USAGE_DB": os.path.join(t, "db", "u.db")}
        self.old = {k: os.environ.get(k) for k in list(self.env) + ["CC_USAGE_PRICES"]}
        os.environ.update(self.env)
        os.environ.pop("CC_USAGE_PRICES", None)

    def tearDown(self):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def main_file(self, lines, mode="w"):
        with open(os.path.join(self.proj, SID + ".jsonl"), mode) as f:
            for d in lines:
                f.write(json.dumps(d) + "\n")

    def sub(self, aid, lines, role="fixer", parent=None, model="claude-sonnet-5-5", mode="w", desc="task"):
        d = os.path.join(self.proj, SID, "subagents")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "agent-%s.jsonl" % aid), mode) as f:
            for x in lines:
                f.write(json.dumps(x) + "\n")
        meta = {"agentType": role, "model": model, "description": desc, "spawnDepth": 1, "finished": True}
        if parent:
            meta["parentAgentId"] = parent
        with open(os.path.join(d, "agent-%s.meta.json" % aid), "w") as f:
            json.dump(meta, f)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cc_usage.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def agents(self):
        conn = cc_usage.connect()
        return {r["agent_id"]: dict(r) for r in conn.execute("SELECT * FROM agents")}


class TestCost(Base):
    def test_dedup_by_request_id(self):
        u = usage(inp=100, out=50, cr=1000, w5=200)
        self.main_file([line("2026-11-20T10:00:00Z", u=u, req="a"),
                        line("2026-11-20T10:00:01Z", u=u, req="a"),   # split line of the same response
                        line("2026-11-20T10:00:02Z", u=u, req="b")])
        self.run_cli("collect", "--quiet")
        m = self.agents()["main"]
        self.assertEqual(m["requests"], 2)
        self.assertEqual(m["output"], 100)
        self.assertEqual(m["cache_read"], 2000)

    def test_cache_bucket_split_and_cost(self):
        u = usage(inp=1000000, out=1000000, cr=1000000, w5=1000000, w1=1000000)
        self.main_file([line("2026-11-20T10:00:00Z", u=u)])
        self.run_cli("collect", "--quiet")
        m = self.agents()["main"]
        self.assertEqual((m["cache_write_5m"], m["cache_write_1h"]), (1000000, 1000000))
        self.assertAlmostEqual(m["cost"], 4 + 5 + 8 + 0.20 + 20)  # opus-5-5, one million of each

    def test_cache_creation_without_split_is_5m(self):
        u = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0,
             "cache_creation_input_tokens": 500}
        self.main_file([line("2026-11-20T10:00:00Z", u=u)])
        self.run_cli("collect", "--quiet")
        self.assertEqual(self.agents()["main"]["cache_write_5m"], 500)

    def test_haiku_long_context_tier(self):
        short = usage(inp=50000, out=1000000)
        long_ = usage(inp=1000000, out=1000000, cr=200000)
        self.main_file([line("2026-11-20T10:00:00Z", model="claude-haiku-5-5", u=short, req="s"),
                        line("2026-11-20T10:00:05Z", model="claude-haiku-5-5", u=long_, req="l")])
        self.run_cli("collect", "--quiet")
        c = cc_usage.connect()
        costs = {r["key"].split("|")[-1]: r["cost"] for r in c.execute("SELECT key, cost FROM requests")}
        self.assertAlmostEqual(costs["s"], 0.10 * 0.05 + 0.50)
        self.assertAlmostEqual(costs["l"], 0.50 + 2.50 + 0.05 * 0.2)

    def test_fast_flag(self):
        u = usage(inp=1000000, out=1000000, speed="fast")
        self.main_file([line("2026-11-20T10:00:00Z", u=u)])
        self.run_cli("collect", "--quiet")
        m = self.agents()["main"]
        self.assertEqual(m["fast"], 1)
        self.assertAlmostEqual(m["cost"], 2 * (4 + 20))

    def test_unknown_model_is_null_and_warns(self):
        self.main_file([line("2026-11-20T10:00:00Z", model="claude-mystery-9", u=usage(inp=10, out=10))])
        rc, out, err = self.run_cli("collect", "--quiet")
        self.assertIn("unknown model", err)
        c = cc_usage.connect()
        self.assertIsNone(c.execute("SELECT cost FROM requests").fetchone()[0])
        self.assertEqual(self.agents()["main"]["unpriced"], 1)

    def test_date_suffix_matches(self):
        p = cc_usage.load_prices()
        self.assertIsNotNone(cc_usage.price_for(p, "claude-haiku-4-5-20251001"))
        self.assertIsNone(cc_usage.price_for(p, "claude-nope"))


class TestAgents(Base):
    def test_lead_rollup_and_retry_chain(self):
        t = "2026-11-20T10:00:%02dZ"
        u = usage(inp=1000000)  # sonnet-5-5: $2; opus-5-5: $4
        self.main_file([line(t % 0, u=u, req="m1")])
        self.sub("lead1", [line(t % 1, u=u, req="l1", agent="lead1")], role="lead", model="claude-opus-5-5")
        self.sub("fixA", [line(t % 2, u=u, req="f1", agent="fixA", model="claude-sonnet-5-5")],
                 parent="lead1")
        self.sub("fixB", [line(t % 3, u=u, req="f2", agent="fixB", model="claude-opus-5-5")],
                 role="fixer-opus", parent="lead1")
        self.run_cli("collect", "--quiet")
        a = self.agents()
        self.assertEqual(a["fixA"]["parent_agent_id"], "lead1")
        self.run_cli("outcome", "fixA", "fail", "--kind", "build", "--missed", "wrong file")
        self.run_cli("outcome", "fixB", "pass", "--kind", "build", "--retry-of", "fixA")
        rc, out, err = self.run_cli("report")
        self.assertEqual(rc, 0)
        wave = out.split("== Lead waves")[1].split("\n== ")[0]
        self.assertIn("$10.00", wave)       # lead 4 + fixer 2 + fixer-opus 4
        chain = out.split("== Cost per accepted")[1].split("\n== ")[0]
        self.assertIn("$6.00", chain)       # chain fixA + fixB = 2 + 4, one accepted
        retries = out.split("== Retries that changed")[1].split("\n== ")[0]
        self.assertIn("fixA", retries)
        self.assertIn("fixB", retries)

    def test_latest_outcome_wins_and_prefix(self):
        self.main_file([line("2026-11-20T10:00:00Z", u=usage(inp=1))])
        self.sub("abcdef1", [line("2026-11-20T10:00:01Z", u=usage(inp=1), agent="abcdef1")])
        self.run_cli("collect", "--quiet")
        self.run_cli("outcome", "abcd", "fail")
        self.run_cli("outcome", "abcdef1", "pass")
        rc, out, err = self.run_cli("report")
        self.assertNotIn("Workers with no recorded outcome (1)", out)
        rc, out, err = self.run_cli("outcome", "zzz", "pass")  # before collect: stored as given
        self.assertEqual(rc, 0)

    def test_active_time_caps_gaps(self):
        self.main_file([line("2026-11-20T10:00:00Z", u=usage(inp=1), req="a"),
                        line("2026-11-20T10:01:00Z", u=usage(inp=1), req="b"),   # 60 s
                        line("2026-11-20T12:00:00Z", u=usage(inp=1), req="c")])  # capped at 300 s
        self.run_cli("collect", "--quiet")
        m = self.agents()["main"]
        self.assertAlmostEqual(m["active_s"], 360)
        self.assertAlmostEqual(m["wall_s"], 7200)

    def test_main_skips_sidechain_lines(self):
        self.main_file([line("2026-11-20T10:00:00Z", u=usage(inp=1), req="a"),
                        line("2026-11-20T10:00:01Z", u=usage(inp=1), req="b", agent="x")])
        self.run_cli("collect", "--quiet")
        self.assertEqual(self.agents()["main"]["requests"], 1)

    def test_incremental_adds_only_new_lines(self):
        u = usage(inp=10, out=5)
        self.main_file([line("2026-11-20T10:00:00Z", u=u, req="a", tools=2)])
        rc, out, err = self.run_cli("collect")
        self.assertIn("collected 1 new lines", out)
        rc, out, err = self.run_cli("collect")
        self.assertIn("collected 0 new lines", out)
        self.main_file([line("2026-11-20T10:00:30Z", u=u, req="b", tools=1)], mode="a")
        rc, out, err = self.run_cli("collect")
        self.assertIn("collected 1 new lines", out)
        m = self.agents()["main"]
        self.assertEqual((m["requests"], m["tool_calls"]), (2, 3))
        self.assertAlmostEqual(m["active_s"], 30)

    def test_partial_last_line_waits(self):
        p = os.path.join(self.proj, SID + ".jsonl")
        full = json.dumps(line("2026-11-20T10:00:00Z", u=usage(inp=1), req="a"))
        with open(p, "w") as f:
            f.write(full + "\n" + full[:20])
        self.run_cli("collect", "--quiet")
        self.assertEqual(self.agents()["main"]["requests"], 1)
        with open(p, "w") as f:
            f.write(full + "\n" + json.dumps(line("2026-11-20T10:00:09Z", u=usage(inp=1), req="b")) + "\n")
        self.run_cli("collect", "--quiet")
        self.assertEqual(self.agents()["main"]["requests"], 2)


class TestWarnings(Base):
    def test_missing_field_warns_with_version(self):
        bad = line("2026-11-20T10:00:00Z", u={"input_tokens": 5, "output_tokens": 5})
        self.main_file([bad])
        rc, out, err = self.run_cli("collect", "--quiet")
        self.assertIn("cache_read_input_tokens", err)
        self.assertIn("2.1.330", err)
        self.assertEqual(rc, 0)

    def test_html_report_is_self_contained(self):
        self.main_file([line("2026-11-20T10:00:00Z", u=usage(inp=1000, out=100))])
        self.sub("fx1", [line("2026-11-20T10:00:01Z", u=usage(inp=1000), agent="fx1")])
        self.run_cli("collect", "--quiet")
        self.run_cli("outcome", "fx1", "pass", "--kind", "build")
        path = os.path.join(self.tmp.name, "r.html")
        rc, out, err = self.run_cli("report", "--html", path)
        with open(path) as f:
            text = f.read()
        self.assertIn("<svg", text)
        self.assertNotIn("http://", text.replace("http://www.w3.org", ""))
        self.assertNotIn("<script", text)
        self.assertIn("prefers-color-scheme:dark", text)


if __name__ == "__main__":
    unittest.main()
