"""Tests for cc-usage on synthetic transcripts. Run: python3 -m unittest usage/test_cc_usage.py"""
import contextlib, fcntl, io, json, os, sqlite3, subprocess, sys, tempfile, unittest

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
        self.env = {"CC_USAGE_CONFIG_DIRS": self.cfg, "CC_USAGE_DB": os.path.join(t, "db", "u.db")}
        self.old = {k: os.environ.get(k) for k in list(self.env) + ["CC_USAGE_PRICES", "CLAUDE_CONFIG_DIR", "HOME"]}
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


def write_profile(root, name, sid, lines):
    proj = os.path.join(root, name, "projects", "-work-proj")
    os.makedirs(proj, exist_ok=True)
    with open(os.path.join(proj, sid + ".jsonl"), "w") as f:
        for d in lines:
            f.write(json.dumps(d) + "\n")


class TestProfiles(Base):
    def two_profiles(self):
        home = os.path.join(self.tmp.name, "home")
        write_profile(home, ".claude", "s-one", [line("2026-11-20T10:00:00Z", u=usage(inp=1000000), req="a", sessionId="s-one")])
        write_profile(home, ".claude_famn", "s-two", [line("2026-11-20T11:00:00Z", u=usage(inp=2000000), req="b", sessionId="s-two")])
        os.makedirs(os.path.join(home, ".claude_empty"))          # no projects/: ignored
        open(os.path.join(home, ".claude.json"), "w").close()     # a file: ignored
        return home

    def test_default_discovery_and_profile_column(self):
        home = self.two_profiles()
        os.environ.pop("CC_USAGE_CONFIG_DIRS")
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        os.environ["HOME"] = home
        self.run_cli("collect", "--quiet")
        prof = {r["session"]: r["profile"] for r in cc_usage.connect().execute("SELECT session, profile FROM agents")}
        self.assertEqual(prof, {"s-one": ".claude", "s-two": ".claude_famn"})

    def test_override_limits_profiles(self):
        home = self.two_profiles()
        os.environ["CC_USAGE_CONFIG_DIRS"] = os.path.join(home, ".claude_famn")
        self.run_cli("collect", "--quiet")
        self.assertEqual({r["profile"] for r in cc_usage.connect().execute("SELECT profile FROM agents")},
                         {".claude_famn"})

    def test_report_profile_filter_and_table(self):
        home = self.two_profiles()
        os.environ["CC_USAGE_CONFIG_DIRS"] = ":".join(os.path.join(home, d) for d in (".claude", ".claude_famn"))
        self.run_cli("collect", "--quiet")
        rc, out, err = self.run_cli("report")
        self.assertIn("Totals by profile", out)
        self.assertIn("Profiles included: .claude, .claude_famn", out)
        prof = out.split("== Totals by profile ==")[1].split("\n== ")[0]
        self.assertIn("$8.00", prof)
        self.assertIn("66.7%", prof)
        rc, out, err = self.run_cli("report", "--profile", "famn")
        self.assertIn("Profiles included: .claude_famn.", out)
        self.assertNotIn(".claude,", out)

    def test_duplicate_session_in_two_profiles_is_skipped(self):
        home = self.two_profiles()
        write_profile(home, ".claude_famn", "s-one", [line("2026-11-20T10:00:00Z", u=usage(inp=5), req="a", sessionId="s-one")])
        os.environ["CC_USAGE_CONFIG_DIRS"] = ":".join(os.path.join(home, d) for d in (".claude", ".claude_famn"))
        rc, out, err = self.run_cli("collect", "--quiet")
        self.assertIn("both .claude and .claude_famn", err)
        self.assertEqual(len(list(cc_usage.connect().execute("SELECT * FROM agents WHERE session='s-one'"))), 1)

    def test_migrates_old_schema_db(self):
        db = os.environ["CC_USAGE_DB"]
        os.makedirs(os.path.dirname(db))
        old = sqlite3.connect(db)
        old.executescript(cc_usage.SCHEMA.replace(", profile TEXT, PRIMARY KEY", ", PRIMARY KEY"))
        old.execute("INSERT INTO agents(session, agent_id, project, role) VALUES('sx','main','p','main')")
        old.execute("INSERT INTO agents(session, agent_id, project, role) VALUES('sy','a1','p','fixer')")
        old.execute("INSERT INTO files VALUES('/h/.claude_lib/projects/-p/sx.jsonl',1,1,1)")
        old.execute("INSERT INTO files VALUES('/h/.claude_syd/projects/-p/sy/subagents/agent-a1.jsonl',1,1,1)")
        old.commit()
        old.close()
        self.assertNotIn("profile", [r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(agents)")])
        self.run_cli("collect", "--quiet")
        prof = {r["session"]: r["profile"] for r in cc_usage.connect().execute("SELECT session, profile FROM agents")}
        self.assertEqual(prof, {"sx": ".claude_lib", "sy": ".claude_syd"})

    def test_concurrent_collect_is_skipped_while_locked(self):
        self.main_file([line("2026-11-20T10:00:00Z", u=usage(inp=1))])
        cc_usage.connect().close()
        lock = open(os.path.join(os.path.dirname(os.environ["CC_USAGE_DB"]), "collect.lock"), "w")
        fcntl.flock(lock, fcntl.LOCK_EX)
        rc, out, err = self.run_cli("collect")
        self.assertEqual(rc, 0)
        self.assertIn("skipped", out)
        self.assertEqual(self.agents(), {})
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
        self.run_cli("collect", "--quiet")
        self.assertIn("main", self.agents())


class TestInstallMerge(unittest.TestCase):
    def test_hooks_merged_once_and_existing_kept(self):
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with tempfile.TemporaryDirectory() as t:
            cfg = os.path.join(t, ".claude_x")
            os.makedirs(cfg)
            mine = {"hooks": [{"type": "command", "command": 'python3 "/elsewhere/hooks/usage-collect.py"', "timeout": 60}]}
            with open(os.path.join(cfg, "settings.json"), "w") as f:
                json.dump({"keep": 1, "hooks": {"SessionEnd": [mine]}}, f)
            env = dict(os.environ, HOME=t, CLAUDE_CONFIG_DIR=cfg, CLAUDE_SETUP_NO_SYSTEM="1")
            for _ in range(2):
                subprocess.run(["bash", os.path.join(repo, "install.sh")], env=env, check=True, capture_output=True)
            with open(os.path.join(cfg, "settings.json")) as f:
                data = json.load(f)
            self.assertEqual(data["keep"], 1)
            self.assertEqual(data["hooks"]["SessionEnd"], [mine])
            sub = data["hooks"]["SubagentStop"]
            self.assertEqual(sub, [{"hooks": [{"type": "command", "timeout": 60,
                                               "command": 'python3 "%s/hooks/usage-collect.py"' % cfg}]}])
            self.assertEqual(len(data["hooks"]["PreToolUse"]), 1)


if __name__ == "__main__":
    unittest.main()
