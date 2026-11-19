#!/usr/bin/env python3
"""Word Quest v11.20-beta1 — public beta checks (headless Chrome / Playwright).
Run: serve v1118/v1119/v1120a/v1120b side by side (see onboarding_v1120_test.py), then python3 tests/beta_v1120_test.py
Versions served side by side at http://localhost:8765/:
  v1118 = main (rollback), v1119 = curriculum-v11.19 Round2 (regression baseline),
  v1120a = onboarding-v11.20 (before), v1120b = this branch (after)."""
import json, os, re, time, traceback
from playwright.sync_api import sync_playwright

BASE = os.environ.get("WQ_BASE", "http://localhost:8765/")
NEW = os.environ.get("WQ_NEW", "v1120b")
SHOTS = os.environ.get("WQ_SHOTS", "beta-shots/"); os.makedirs(SHOTS, exist_ok=True)
RESULTS, PAGE_ERRORS = [], []
SEED_JS = """(()=>{ let s=%d>>>0; Math.random=function(){ s=(s+0x6D2B79F5)>>>0; let t=s; t=Math.imul(t^(t>>>15),t|1); t^=t+Math.imul(t^(t>>>7),t|61); return ((t^(t>>>14))>>>0)/4294967296; }; })();"""

def check(tid, name, ok, detail=""):
    RESULTS.append((tid, name, bool(ok), detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)))
    print(("PASS" if ok else "FAIL"), tid, name, ("— " + str(detail)[:200]) if detail else "")

class App:
    def __init__(self, browser, ver=NEW, width=420, height=900, seed=None, storage=None, mobile=False, block_lt=False):
        self.ctx = browser.new_context(viewport={"width": width, "height": height}, is_mobile=mobile, has_touch=mobile, accept_downloads=True)
        if seed is not None: self.ctx.add_init_script(SEED_JS % seed)
        if storage is not None:
            self.ctx.add_init_script("if(!sessionStorage.getItem('__seeded')){ localStorage.setItem('wordquest_v1', %s); sessionStorage.setItem('__seeded','1'); }" % json.dumps(storage))
        self.lt_calls = 0
        def lt(route):
            self.lt_calls += 1; route.abort()
        self.ctx.route("**/api.languagetool.org/**", lt)
        self.ctx.route("**/fonts.googleapis.com/**", lambda r: r.abort())
        self.page = self.ctx.new_page(); self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.ver = ver
        self.page.goto(BASE + ver + ".html"); self.page.wait_for_function("typeof S!=='undefined'")
    def js(self, code, arg=None): return self.page.evaluate(code, arg) if arg is not None else self.page.evaluate(code)
    def text(self): return self.page.inner_text("#app")
    def click(self, name, exact=False): self.page.get_by_role("button", name=name, exact=exact).first.click()
    def stored(self): return self.js("localStorage.getItem('wordquest_v1')")
    def data(self): return json.loads(self.stored())
    def reload(self): self.page.reload(); self.page.wait_for_function("typeof S!=='undefined'")
    def shot(self, name, full=True): self.page.screenshot(path=SHOTS + name + ".png", full_page=full)
    def gate_open(self): return self.js("!!(document.getElementById('pg_in'))")
    def pass_gate(self, wrong_first=False):
        self.page.wait_for_selector("#pg_in")
        if wrong_first:
            self.page.fill("#pg_in", "1"); self.page.locator("#pgate button", has_text="OK").click()
        self.page.fill("#pg_in", self.js("PG.ans")); self.page.locator("#pgate button", has_text="OK").click()
    def cancel_gate(self): self.page.locator("#pgate .row button").first.click()
    def close(self):
        PAGE_ERRORS.extend(f"[{self.ver}] {e}" for e in self.errors); self.ctx.close()

SIM_MISSION = """(k)=>{ choose(k); startMission(); M.all.forEach((id,i)=>{ M.ok[id] = (i%4!==0); }); M.coins=120; finish(); return Object.keys(P().words).length; }"""
CONTENT = """()=>({words:Object.keys(WORDS).length, fams:FAMS.length, famQ:FAMS.reduce((a,f)=>a+f[4].length,0), passages:PASSAGES.length, basics:BASICS.length,
  mix:JSON.stringify(MIX), int:JSON.stringify(INT), egg:EGG, review:Object.values(REVIEW_EX).reduce((a,b)=>a+b.length,0), rel:Object.keys(REL).length,
  stages:STAGES.map(s=>s.id+':'+s.words.length).join(' ')})"""
ENGINE = "()=>[startMission,{toString:()=>finish.toString().split('render(')[0]},planMix,mixReviews,balanceMix,pickNew,dueList,chooseSentences,relQ,distractors,screenQuiz,resolveQ,typeCheck,startPassages,pasAnswer,diagNext,diagSave,diagItems,diagStartLevel,hatch,backupText,saveHistory,startBasics,startFamPractice].map(f=>f.toString()).join('\\n')"
MISSION_SIG = """(k)=>{ choose(k); startMission(); return JSON.stringify({news:M.news, rev:M.reviews, q:M.q.map(q=>q.id+'/'+q.t+'/'+(q.sk||''))}); }"""

def sign_up(app, name, grade, daily=None):
    p = app.page
    p.fill("#ns_name", name)
    p.locator("#ns_grades button", has_text=re.compile(r"^%d$" % grade)).first.click()
    if daily is not None: p.get_by_role("button", name=f"{daily} new words a day", exact=True).click()
    app.click("Continue ▶")

def do_diag(app, pattern):
    p = app.page
    for n in pattern:
        for i in range(8):
            if i < n: p.locator(".opts button.opt").evaluate_all("bs=>bs.find(x=>x.getAttribute('onclick')==='diagAnswer(true)').click()")
            else: app.click("🤔 I don't know")
    for i in range(6): p.locator(".opts button.opt").evaluate_all("bs=>bs.find(x=>x.getAttribute('onclick')==='diagAnswer(true)').click()")

def make_legacy(browser):
    a = App(browser, "v1118", seed=11)
    a.js(SIM_MISSION, "a"); a.js(SIM_MISSION, "b")
    a.js("()=>{ choose('a'); P().coins+=2400; save(); screenShop(); hatch(); }"); time.sleep(0.8)
    a.js("()=>{ choose('b'); P().coins+=1200; save(); screenShop(); hatch(); }"); time.sleep(0.8)
    a.js("()=>{ S.lastBackup=today()-3; S.profiles.a.days[today()-1]=true; S.profiles.a.days[today()-2]=true; save(); screenProfiles(); }")
    v18 = a.stored(); a.close()
    b = App(browser, "v1119", seed=12, storage=v18)
    b.js("()=>{ diagStart('a'); DG.items.forEach(()=>diagAnswer(true)); }")
    b.js("()=>{ for(let i=0;i<40 && DG.phase==='words';i++) diagAnswer(i%3===0); while(DG.phase==='basics' && DG.i<DG.bitems.length) diagAnswer(DG.i%2===0); }")
    b.js("()=>{ diagChoose(false); }")
    b.js("()=>{ choose('b'); startPassages(); for(let i=0;i<5;i++){ const bs=[...document.querySelectorAll('#popts .opt')]; (i%2?bs[0]:bs.find(x=>x.dataset.ok==='true')).click(); PP.i++; } screenProfiles(); }")
    legacy = b.stored(); b.close()
    return legacy

TARGETS_JS = """()=>[...document.querySelectorAll('button, input, select, label.btn, textarea')].map(e=>e.type==='checkbox'&&e.closest('label')?e.closest('label'):e).filter(e=>{ const r=e.getBoundingClientRect(); return r.width>0 && r.height>0 && getComputedStyle(e).visibility!=='hidden'; })
  .map(e=>{ const r=e.getBoundingClientRect(); return {t:(e.innerText||e.getAttribute('aria-label')||e.id||e.tagName).trim().slice(0,30), w:Math.round(r.width), h:Math.round(r.height)}; }).filter(x=>x.w<44||x.h<44)"""
FONT_JS = """()=>{ let min=99, at=''; const w=document.createTreeWalker(document.getElementById('app'), NodeFilter.SHOW_TEXT); let n; while(n=w.nextNode()){ if(!n.textContent.trim()) continue; const e=n.parentElement, r=e.getBoundingClientRect(); if(!r.width) continue; const f=parseFloat(getComputedStyle(e).fontSize); if(f<min){ min=f; at=n.textContent.trim().slice(0,30); } } return [min,at]; }"""
NAMES_JS = """()=>[...document.querySelectorAll('#app button, #app input, #app select, #pgate input')].filter(e=>e.offsetParent!==null && !(e.innerText||'').trim() && !e.getAttribute('aria-label') && !(e.labels&&e.labels.length) && !e.placeholder).map(e=>e.outerHTML.slice(0,80))"""

def a11y(app, where):
    small = app.js(TARGETS_JS); fmin = app.js(FONT_JS); noname = app.js(NAMES_JS)
    over = app.js("document.documentElement.scrollWidth > window.innerWidth + 1")
    return {"where": where, "small": small, "minfont": fmin, "noname": noname, "hscroll": over}

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])

        # ===== 1. current code and data =====
        c19, cn = App(browser, "v1119"), App(browser, NEW)
        k19, kn = c19.js(CONTENT), cn.js(CONTENT)
        check("1", "content identical to v11.19 Round2", k19 == kn, kn)
        check("1", "2,785 word cards · 393 Word Families · 60 SAT passages · 27 basic words", (kn["words"], kn["fams"], kn["passages"], kn["basics"]) == (2785, 393, 60, 27))
        check("1", "learning engine code identical to v11.19 (mission, review schedule incl. finish() scoring, quiz, passages, placement scoring, hatch, backup format; only the finish screen text differs)", c19.js(ENGINE) == cn.js(ENGINE))
        c19.close(); cn.close()
        legacy = make_legacy(browser); L = json.loads(legacy)
        open(SHOTS + "legacy_data.json", "w").write(legacy)
        sig = {}
        for ver in ("v1119", NEW):
            x = App(browser, ver, seed=99, storage=legacy); a_ = x.js(MISSION_SIG, "a"); x.close()
            x = App(browser, ver, seed=99, storage=legacy); b_ = x.js(MISSION_SIG, "b"); x.close()
            sig[ver] = (a_, b_)
        check("1", "existing students' Today's Mission identical to v11.19 (words, reviews, question types, sentences)", sig["v1119"] == sig[NEW])

        # ===== 7. first visit =====
        n = App(browser, NEW)
        t = n.text()
        check("6", "first visit: Welcome, no student names, no built-in profiles", "Start Learning" in t and "막내" not in t and "셋째" not in t and n.data()["profiles"] == {})
        check("6", "first visit: grammar check (outside service) OFF by default", n.data().get("extGrammar") is False)
        n.shot("A01_welcome")
        n.click("🔒 About your data"); t = n.text()
        check("6", "About your data explains: no real name/email, browser-only storage, loss risk, outside services", all(x in t for x in ["No account", "Only in this browser", "Clearing browsing data", "Google Fonts", "LanguageTool", "No ads"]))
        n.shot("A02_about_data")
        n.click("Back")
        # keyboard-only sign-up
        n.page.get_by_role("button", name="Start Learning ▶").focus(); n.page.keyboard.press("Enter")
        n.page.keyboard.type("Kiki")
        n.page.keyboard.press("Tab")                      # → grade 4
        for _ in range(3): n.page.keyboard.press("Tab")   # → grade 7
        n.page.keyboard.press("Enter")
        n.page.focus("#ns_name"); n.page.keyboard.press("Enter")
        check("6", "keyboard only: type nickname, Tab to grade, Enter to choose, Enter to continue", n.js("Object.keys(S.profiles).length") == 1 and n.js("P().grade") == "7th grade", n.js("P() && P().grade"))
        n.close()

        # ===== main shared device: 2 legacy students + new students =====
        m = App(browser, NEW, seed=5, storage=legacy)
        check("3", "legacy data opens unchanged (no field added, grammar check keeps its old ON behaviour)", m.data() == L and m.js("grammarOn()") is True)
        check("2", "student list has Parent Settings behind a parent check", "Parent Settings" in m.text())
        ids = {}
        # grade 4: placement → Use This Level → parent check (wrong answer first)
        for (nm, gr, dl) in [("Alex", 4, 5), ("Jordan", 7, 8), ("Sam", 10, 10), ("Alex", 12, 3)]:
            m.click("➕ Add Student"); sign_up(m, nm, gr, dl)
            pid = m.js("S.active"); ids[(nm, gr)] = pid
            p = m.js("P()")
            check("4", f"{nm} grade {gr}: own ID, grade, daily {dl}, temporary level by grade", pid.startswith("p_") and p["grade"] == f"{gr}th grade" and p["daily"] == dl and p["stage"] == ("m" if gr >= 7 else "e"))
            if gr == 4:
                m.shot("A03_placement_intro")
                m.click("Take the Placement Check ▶"); m.click("Start ▶"); do_diag(m, [8, 3])
                m.shot("A04_placement_result")
                m.click("Use This Level")
                check("2", "applying the placement result asks a parent", m.gate_open())
                m.shot("A05_parent_check")
                m.pass_gate(wrong_first=True)
                check("2", "wrong parent answer is refused, right answer applies Elementary", m.js("P().stage") == "e" and m.js("P().diag.chosen") == "e")
            elif gr == 7:
                m.click("Take the Placement Check ▶"); m.click("Start ▶"); do_diag(m, [7, 7, 6])
                check("4", "grade 7: M 7, H 7, S 6 → suggests High School", m.js("P().diag.suggested") == "h")
                m.click("Use This Level"); m.cancel_gate()
                check("2", "'Not now' keeps the starting level and leaves the suggestion pending", m.js("P().stage") == "m" and m.js("P().diag.chosen") is None)
                t = m.text()
                check("4", "home shows the pending suggestion and how to apply it", "suggests" in t and "Ask a parent to apply it" in t)
                m.shot("A06_home_pending_suggestion")
            elif gr == 10:
                m.click("Start with the suggested level (🔥 Middle School)")
                check("4", "grade 10 skip → Middle School (temporary) + home says it is temporary", m.js("P().stage") == "m" and "level is temporary" in m.text())
                m.shot("A07_home_temporary_level")
            else:
                m.click("Take the Placement Check ▶"); m.click("Start ▶"); do_diag(m, [0, 0])
                check("4", "grade 12, all 'I don't know' → suggests Elementary", m.js("P().diag.suggested") == "e")
                m.click("Choose Another Level"); m.page.locator("#dgo button", has_text="High School").click(); m.pass_gate()
                check("2", "Choose Another Level (High School) applied after parent check", m.js("P().stage") == "h")
            t = m.text()
            check("5", f"{nm} g{gr}: home shows level, new words, reviews, progress and More practice; Start Mission is first button",
                  all(x in t for x in ["Today's Mission", "new words", "to review", "My progress", "More practice", "Placement check"]) and m.page.locator("#app .btn").first.inner_text().startswith("Start Mission"))
            m.click("◀ 👥")
        m.shot("A08_student_list")
        alexes = [k for k in m.js("Object.keys(S.profiles)") if m.js(f"S.profiles['{k}'].name") == "Alex"]
        check("3", "two students named Alex are different IDs", len(alexes) == 2 and alexes[0] != alexes[1])

        # apply the pending suggestion from home (Jordan)
        jor = ids[("Jordan", 7)]
        m.js(f"choose('{jor}')"); m.click("Ask a parent to apply it"); m.pass_gate()
        check("2", "pending suggestion applied from home after parent check", m.js("P().stage") == "h" and m.js("P().diag.chosen") == "h")
        # level change from the Levels grid needs a parent; Cancel keeps it
        m.page.get_by_role("button", name="SAT Prep").click()
        check("2", "tapping another level asks a parent", m.gate_open())
        m.cancel_gate()
        check("2", "Cancel keeps the level", m.js("P().stage") == "h")
        m.page.get_by_role("button", name="SAT Prep").click(); m.pass_gate()
        check("2", "level changes after parent check; words and history untouched", m.js("P().stage") == "s")
        # retake placement from home: find it easily
        check("4", "placement check can be retaken from home (More practice)", m.page.get_by_role("button", name="🧭 Placement check").count() == 1)

        # mission for Sam → only Sam changes (records do not mix)
        sam = ids[("Sam", 10)]
        others_before = {k: v for k, v in m.data()["profiles"].items() if k != sam}
        m.js(f"choose('{sam}')"); m.click("Start Mission ▶")
        m.shot("A09_mission_learn")
        m.js("()=>{ M.all.forEach((id,i)=>M.ok[id]=i%3!==0); M.coins=80; finish(); }")
        t = m.text()
        check("4", "after the mission the student is told what to do next", "What's next?" in t and "Come back tomorrow" in t)
        m.shot("A10_mission_clear")
        others_after = {k: v for k, v in m.data()["profiles"].items() if k != sam}
        check("3", "Sam's mission changes only Sam (other 5 students identical)", others_before == others_after and len(m.data()["profiles"][sam]["words"]) > 0)
        m.js("screenHome()"); t = m.text()
        check("4", "home after the mission says done and come back tomorrow", "Today's Mission: done!" in t and "come back tomorrow" in t)
        m.shot("A11_home_done")

        # Parent Settings
        m.click("◀ 👥"); m.click("👪 Parent Settings")
        check("2", "Parent Settings asks a parent first", m.gate_open())
        m.cancel_gate()
        check("2", "Cancel stays on the student list", "Who's learning today?" in m.text())
        m.click("👪 Parent Settings"); m.pass_gate()
        t = m.text()
        check("2", "Parent Settings is clearly a parent area (title, not-a-lock note, students, data & privacy)", all(x in t for x in ["Parent Settings", "not a lock", "Students", "Data & privacy", "Progress lives only in this browser"]))
        m.shot("A12_parent_settings")
        # delete second Alex: wrong name refused, right name deletes only that ID
        before = m.data()["profiles"]
        m.page.locator(".card", has=m.page.locator(f"#n_{alexes[1]}")).get_by_role("button", name="🗑️ Delete student").click()
        m.page.fill("#cfin", "Alex K"); m.page.click("#cfgo")
        check("2", "delete: wrong nickname refused", "does not match" in m.text() and alexes[1] in m.js("Object.keys(S.profiles)"))
        m.shot("A13_delete_confirm")
        m.page.fill("#cfin", "Alex"); m.page.click("#cfgo")
        after = m.data()["profiles"]
        check("2", "delete removes only that student (other Alex and everyone else unchanged)", alexes[1] not in after and all(after[k] == before[k] for k in after))
        # reset Sam: typed confirmation, keeps the student
        m.page.locator(".card", has=m.page.locator(f"#n_{sam}")).get_by_role("button", name="🔄 Reset progress").click()
        m.page.fill("#cfin", "Sam"); m.page.click("#cfgo")
        sp = m.data()["profiles"][sam]
        check("2", "reset clears Sam's words/coins/pets but keeps Sam on the list", sp["words"] == {} and sp["coins"] == 0 and sp["name"] == "Sam")
        # PIN
        m.page.fill("#pinin", "12"); m.click("Save PIN")
        check("2", "PIN must be 4 digits", "exactly 4 digits" in m.text())
        m.page.fill("#pinin", "4321"); m.click("Save PIN")
        m.click("◀ Save"); m.click("👪 Parent Settings")
        check("2", "with a PIN set, the parent check asks for the PIN", "Parent PIN" in m.page.inner_text("#pgate") and m.js("PG.ans") == "4321")
        m.shot("A14_parent_check_pin")
        m.page.get_by_role("button", name="Forgot the PIN?").click()
        check("2", "Forgot the PIN → grown-up math question instead", "Grown-ups: what is" in m.page.inner_text("#pgate"))
        m.pass_gate()
        m.page.get_by_role("button", name="Remove PIN").click()
        check("2", "PIN can be removed", "parentPin" not in m.data())
        m.click("◀ Save")
        # existing students byte-identical through everything
        D = m.data()
        check("3", "existing students (a, b) byte-identical after sign-ups, placements, gates, level changes, delete, reset, PIN, settings save",
              json.dumps(D["profiles"]["a"], ensure_ascii=False) == json.dumps(L["profiles"]["a"], ensure_ascii=False) and json.dumps(D["profiles"]["b"], ensure_ascii=False) == json.dumps(L["profiles"]["b"], ensure_ascii=False))
        check("3", "existing reward message, backup date and grammar setting kept", D["reward"] == L["reward"] and D.get("lastBackup") == L.get("lastBackup") and "extGrammar" not in D)
        backup = m.js("backupText()")
        m.close()

        # ===== grammar check: no outside call when OFF, old behaviour when ON =====
        g = App(browser, NEW)
        g.click("Start Learning ▶"); sign_up(g, "Lee", 5); g.click("Start with the suggested level (🌱 Elementary)")
        g.js("()=>{ startMission(); M.qi=M.q.length; screenBonus(); }")
        w = g.js("WORDS[M.bonus].w")
        g.page.fill("#mine", f"I think the word {w} is useful in my class today."); g.click("Submit")
        time.sleep(1.3)
        check("6", "grammar check OFF: no request to LanguageTool; sentence accepted", g.lt_calls == 0 and "Mission Clear" in g.text())
        g.close()
        g = App(browser, NEW, storage=legacy)
        g.js("()=>{ choose('a'); startMission(); M.qi=M.q.length; screenBonus(); }")
        w = g.js("WORDS[M.bonus].w")
        g.page.fill("#mine", f"I think the word {w} is useful in my class today."); g.click("Submit")
        time.sleep(1.5)
        check("3", "existing browser keeps grammar check ON (request attempted; offline → bonus still given)", g.lt_calls == 1)
        g.close()

        # ===== backup reminder =====
        r = App(browser, NEW, storage=json.dumps(dict(L, lastBackup=L["lastBackup"] - 20)))
        check("3", "backup reminder appears when the last backup is 14+ days old", "Time for a backup" in r.text())
        r.shot("A15_backup_reminder")
        r.click("Remind me later")
        check("3", "'Remind me later' hides it for 7 days", "Time for a backup" not in r.text() and r.js("S.bkSnooze") == r.js("today()+7"))
        r.close()
        r = App(browser, NEW, storage=legacy)
        check("3", "no reminder when the last backup is recent", "Time for a backup" not in r.text())
        r.close()

        # ===== moving to another device =====
        for label, txt in [("v11.20-beta backup", backup),
                           ("v11.18/v11.19 backup", json.dumps({"app": "wordquest", "v": "11.19", "data": L})),
                           ("v11.20 onboarding backup", None)]:
            if txt is None:
                o = App(browser, "v1120a", storage=legacy); o.js("()=>{ screenNewStudent(); $('ns_name').value='Old'; NS.grade=8; nsCreate(); onbSkip(); }"); txt = o.js("backupText()"); o.close()
            d = App(browser, NEW)
            d.click("📂 Restore Progress"); d.click("⌨️ Restore from code"); d.page.fill("#rcode", txt); d.click("Restore", exact=True)
            if label.startswith("v11.20-beta"): d.shot("A16_restore_confirm")
            d.page.click("#rgo")
            want = json.loads(txt)["data"]["profiles"]
            check("3", f"new device restores {label} exactly ({len(want)} students)", d.data()["profiles"] == want)
            d.close()
        # restore from a file
        open("/tmp/wq_backup.json", "w").write(backup)
        d = App(browser, NEW)
        d.click("📂 Restore Progress"); d.page.set_input_files("input[type=file]", "/tmp/wq_backup.json"); d.page.wait_for_selector("#rgo"); d.page.click("#rgo")
        check("3", "restore from a backup file works", d.data()["profiles"] == json.loads(backup)["data"]["profiles"])
        check("3", "the progress that was replaced is kept as a copy in the browser", d.js("!!localStorage.getItem('wordquest_v1_before_restore')"))
        d.close()

        # ===== wrong backups =====
        bads = {"not JSON": "hello", "no students": '{"a":1}', "bad ID": json.dumps({"profiles": {"x'onclick": {"name": "x"}}}),
                "words is a list": json.dumps({"profiles": {"a": {"name": "x", "words": []}}}), "unknown level": json.dumps({"profiles": {"a": {"name": "x", "stage": "z"}}})}
        d = App(browser, NEW, storage=legacy)
        d.js("openParent()"); d.pass_gate()
        for lab, txt in bads.items():
            d.click("⌨️ Restore from code"); d.page.fill("#rcode", txt); d.click("Restore", exact=True)
            ok = ("can't be used" in d.text() or "doesn't look like" in d.text()) and d.page.locator("#rgo").count() == 0 and d.data() == L
            check("7", f"wrong backup refused, nothing changed: {lab}", ok)
        d.shot("A17_wrong_backup")
        open("/tmp/wq_bad.json", "w").write("{broken")
        d.page.set_input_files("#bkcard input[type=file]", "/tmp/wq_bad.json"); time.sleep(0.3)
        check("7", "wrong backup file refused", "doesn't look like" in d.text() and d.data() == L)
        x = json.loads(backup); x["data"]["profiles"]["a"]["color"] = "red;background:url(https://x.test/a)"
        d.click("⌨️ Restore from code"); d.page.fill("#rcode", json.dumps(x)); d.click("Restore", exact=True); d.page.click("#rgo")
        check("7", "unsafe color in a backup is replaced with a plain color", d.data()["profiles"]["a"]["color"] == "#ff6b3d")
        d.close()

        # ===== save failure / damaged data =====
        f = App(browser, NEW, storage=legacy)
        f.js("()=>{ Storage.prototype.setItem=function(){ throw new Error('QuotaExceededError'); }; choose('a'); }")
        check("7", "save failure shows a warning", "did not save the latest progress" in f.text())
        f.shot("A18_save_failed")
        f.js("()=>{ screenRestore(); }")
        f.click("⌨️ Restore from code"); f.page.fill("#rcode", backup); f.click("Restore", exact=True); f.page.click("#rgo")
        check("7", "restore while storage is failing tells the parent it was not saved", "could not save it" in f.text())
        f.close()
        bad = legacy[:len(legacy)//2]
        c = App(browser, NEW, storage=bad)
        check("7", "damaged saved data → recovery screen, nothing overwritten", "could not be read" in c.text() and c.stored() == bad)
        c.close()

        # ===== rollback: v11.18 and v11.19 read the beta backup =====
        for old in ("v1118", "v1119"):
            o = App(browser, old)
            o.js("(t)=>{ document.body.insertAdjacentHTML('beforeend','<div id=\"bkmsg\"></div>'); restoreText(t); $('rgo').click(); }", backup)
            err = None
            try:
                for k in o.js("Object.keys(S.profiles)"): o.js(f"()=>{{ choose('{k}'); screenHome(); startMission(); screenHome(); }}")
            except Exception as e: err = str(e)
            check("4c", f"{old} opens a v11.20-beta backup: all students, home and mission work, no errors", err is None and not o.errors and len(o.js("Object.keys(S.profiles)")) == len(json.loads(backup)["data"]["profiles"]), f"{err} {o.errors[:1]}")
            back = o.js("backupText()"); o.close()
            q = App(browser, NEW); q.js("(t)=>{ screenRestore(); restoreText(t); $('rgo').click(); }", back)
            check("4c", f"backup saved again by {old} reads back into v11.20-beta", q.data()["profiles"] == json.loads(back)["data"]["profiles"])
            q.close()

        # ===== 6. mobile, touch size, text size, labels =====
        rep = []
        for (wd, ht, tag, mob) in [(375, 812, "375", True), (420, 900, "420", True), (820, 1180, "820", True), (1280, 900, "1280", False)]:
            v = App(browser, NEW, width=wd, height=ht, mobile=mob, storage=json.dumps(json.loads(backup)["data"]))
            screens = [("student list", "screenProfiles()"), ("home", f"choose('{ids[('Jordan',7)]}')"), ("parent settings", "screenSettings()"), ("about", "screenAbout()")]
            for (where, call) in screens:
                v.js(call); rep.append(dict(a11y(v, where), size=tag))
                if tag == "375": v.shot(f"A19_{where.replace(' ','_')}_375")
            v.close()
            v = App(browser, NEW, width=wd, height=ht, mobile=mob)
            rep.append(dict(a11y(v, "welcome"), size=tag)); v.click("Start Learning ▶"); rep.append(dict(a11y(v, "sign-up"), size=tag))
            if tag == "375": v.shot("A20_signup_375")
            v.close()
        hs = [r_ for r_ in rep if r_["hscroll"]]
        check("6", "no sideways scrolling at 375/420/820/1280 px (welcome, sign-up, list, home, parent settings, about)", not hs, hs)
        small = {(r_["where"], s_["t"], s_["w"], s_["h"]) for r_ in rep for s_ in r_["small"]}
        open(SHOTS + "a11y_report.json", "w").write(json.dumps(rep, ensure_ascii=False, indent=1))
        check("6", "touch targets ≥ 44×44 px on these screens", not small, sorted(small)[:12])
        fmin = min(r_["minfont"][0] for r_ in rep)
        check("6", "smallest text ≥ 12 px", fmin >= 12, [r_["minfont"] for r_ in rep if r_["minfont"][0] == fmin][:1])
        nn = {x for r_ in rep for x in r_["noname"]}
        check("6", "every button and field has a readable name", not nn, list(nn)[:5])

        # ===== before / after screens (onboarding-v11.20 vs beta) =====
        for ver, tag in (("v1120a", "before"), (NEW, "after")):
            s_ = App(browser, ver, seed=7, storage=backup and json.dumps(json.loads(backup)["data"]))
            s_.js("screenProfiles()"); s_.shot(f"B_{tag}_1_student_list")
            s_.js(f"choose('{ids[('Jordan',7)]}')"); s_.shot(f"B_{tag}_2_home")
            s_.js("()=>{ startMission(); M.all.forEach(id=>M.ok[id]=true); M.coins=50; finish(); }"); s_.shot(f"B_{tag}_3_mission_clear")
            s_.js("screenSettings()"); s_.shot(f"B_{tag}_4_settings")
            s_.close()
            w_ = App(browser, ver); w_.shot(f"B_{tag}_0_welcome"); w_.close()
        browser.close()
    check("all", "no JavaScript errors on any page", not PAGE_ERRORS, PAGE_ERRORS[:3])

if __name__ == "__main__":
    try: main()
    except Exception:
        traceback.print_exc(); RESULTS.append(("crash", traceback.format_exc().splitlines()[-1], False, ""))
    json.dump(RESULTS, open(SHOTS + "results.json", "w"), ensure_ascii=False, indent=1)
    print(f"\n{sum(r[2] for r in RESULTS)}/{len(RESULTS)} passed")
