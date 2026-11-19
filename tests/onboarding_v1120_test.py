#!/usr/bin/env python3
"""Word Quest v11.20 onboarding — regression + A1–A12 checks in headless Chrome (Playwright).
Serve three versions side by side, then run:
  mkdir site && git show origin/main:index.html > site/v1118.html
  git show origin/curriculum-v11.19:index.html > site/v1119.html && cp index.html site/v1120.html
  (cd site && python3 -m http.server 8765 &) ; python3 tests/onboarding_v1120_test.py
v1118 = old main (rollback check), v1119 = Round2 baseline (regression), v1120 = this branch."""
import json, sys, time, traceback
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8765/"
import os
SHOTS = os.environ.get("WQ_SHOTS", "test-shots/"); os.makedirs(SHOTS, exist_ok=True)
RESULTS = []          # (id, name, ok, detail)
PAGE_ERRORS = []

SEED_JS = """(()=>{ let s=%d>>>0; Math.random=function(){ s=(s+0x6D2B79F5)>>>0; let t=s; t=Math.imul(t^(t>>>15),t|1); t^=t+Math.imul(t^(t>>>7),t|61); return ((t^(t>>>14))>>>0)/4294967296; }; })();"""

def check(tid, name, ok, detail=""):
    RESULTS.append((tid, name, bool(ok), detail))
    print(("PASS" if ok else "FAIL"), tid, name, ("— " + str(detail)) if detail else "")

class App:
    """One browser context = one fresh browser profile (its own localStorage)."""
    def __init__(self, browser, ver="v1120", width=420, height=900, seed=None, storage=None, mobile=False):
        self.ctx = browser.new_context(viewport={"width": width, "height": height}, is_mobile=mobile, has_touch=mobile, accept_downloads=True)
        if seed is not None:
            self.ctx.add_init_script(SEED_JS % seed)
        if storage is not None:   # put saved data in place before the app script runs (first load only)
            self.ctx.add_init_script("if(!sessionStorage.getItem('__seeded')){ localStorage.setItem('wordquest_v1', %s); sessionStorage.setItem('__seeded','1'); }" % json.dumps(storage))
        self.page = self.ctx.new_page()
        self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.ver = ver
        self.page.goto(BASE + ver + ".html")
        self.page.wait_for_function("typeof S!=='undefined'")
    def js(self, code, arg=None):
        return self.page.evaluate(code, arg) if arg is not None else self.page.evaluate(code)
    def text(self):
        return self.page.inner_text("#app")
    def click(self, text, exact=False):
        self.page.get_by_role("button", name=text, exact=exact).first.click()
    def stored(self):
        return self.js("localStorage.getItem('wordquest_v1')")
    def reload(self):
        self.page.reload(); self.page.wait_for_function("typeof S!=='undefined'")
    def shot(self, name, full=True):
        self.page.screenshot(path=SHOTS + name + ".png", full_page=full)
    def close(self):
        PAGE_ERRORS.extend(f"[{self.ver}] {e}" for e in self.errors)
        self.ctx.close()

# ---------------------------------------------------------------- helpers run inside the page
SIM_MISSION = """(k)=>{ choose(k); startMission(); M.all.forEach((id,i)=>{ M.ok[id] = (i%4!==0); }); M.coins=120; finish(); return Object.keys(P().words).length; }"""
CONTENT = """()=>({words:Object.keys(WORDS).length, cards:STAGES.reduce((a,s)=>a+s.words.length,0), book:STAGES.reduce((a,s)=>a+((s.book||s.words).length),0),
  fams:FAMS.length, famQ:FAMS.reduce((a,f)=>a+f[4].length,0), passages:(typeof PASSAGES!=='undefined'?PASSAGES.length:null),
  basics:(typeof BASICS!=='undefined'?BASICS.length:null), mix:JSON.stringify(MIX), int:JSON.stringify(INT), egg:EGG,
  review:Object.values(REVIEW_EX).reduce((a,b)=>a+b.length,0), rel:Object.keys(REL).length, stages:STAGES.map(s=>s.id+':'+s.words.length).join(' ')})"""
MISSION_SIG = """(k)=>{ choose(k); startMission(); return JSON.stringify({news:M.news, rev:M.reviews, q:M.q.map(q=>q.id+'/'+q.t+'/'+(q.sk||''))}); }"""

def ui_new_student(app, name, grade, daily=None, color_idx=None):
    """Fill the sign-up form through the screen (clicks and typing)."""
    p = app.page
    p.fill("#ns_name", name)
    p.locator("#ns_grades button", has_text=str(grade)).filter(has_text=__import__('re').compile(r"^%d$" % grade)).first.click()
    if daily is not None:
        p.locator("button", has_text=__import__('re').compile(r"^%d$" % daily)).last.click()
    app.click("Continue ▶")

def do_diag(app, pattern):
    """Answer the placement check: pattern = list of correct-answer counts for each level shown, e.g. [8,7,3]."""
    p = app.page
    for n in pattern:
        for i in range(8):
            if i < n:
                p.locator(".opts button.opt").filter(has_not_text="I don't know").evaluate_all(
                    "bs=>{ const b=bs.find(x=>x.getAttribute('onclick')==='diagAnswer(true)'); b.click(); }")
            else:
                app.click("🤔 I don't know")
    # basic words phase (6 items): answer all correctly
    for i in range(6):
        p.locator(".opts button.opt").evaluate_all("bs=>{ const b=bs.find(x=>x.getAttribute('onclick')==='diagAnswer(true)'); b.click(); }")

# ---------------------------------------------------------------- build legacy data (v11.18 → v11.19 use)
def make_legacy(browser):
    a = App(browser, "v1118", seed=11)
    a.js(SIM_MISSION, "a"); a.js(SIM_MISSION, "b")
    a.js("()=>{ choose('a'); P().coins+=2400; save(); screenShop(); hatch(); }"); time.sleep(0.8)
    a.js("()=>{ choose('b'); P().coins+=1200; save(); screenShop(); hatch(); }"); time.sleep(0.8)
    a.js("()=>{ S.lastBackup=today()-3; S.profiles.a.days[today()-1]=true; S.profiles.a.days[today()-2]=true; save(); screenProfiles(); }")
    v18 = a.stored(); a.close()
    b = App(browser, "v1119", seed=12, storage=v18)
    b.js("()=>{ diagStart('a'); DG.items.forEach(()=>diagAnswer(true)); }")      # a: passes Elementary …
    b.js("()=>{ for(let i=0;i<40 && DG.phase==='words';i++) diagAnswer(i%3===0); while(DG.phase==='basics' && DG.i<DG.bitems.length) diagAnswer(DG.i%2===0); }")
    b.js("()=>{ diagChoose(false); }")
    b.js("()=>{ choose('b'); startPassages(); for(let i=0;i<5;i++){ const bs=[...document.querySelectorAll('#popts .opt')]; (i%2?bs[0]:bs.find(x=>x.dataset.ok==='true')).click(); PP.i++; } screenProfiles(); }")
    legacy = b.stored(); b.close()
    return legacy

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])

        # ============ A11 / A7: content and mission behaviour identical to v11.19 ============
        c19 = App(browser, "v1119"); c20 = App(browser, "v1120")
        k19, k20 = c19.js(CONTENT), c20.js(CONTENT)
        check("A11", "content identical to v11.19 (cards, families, passages, basics, review sentences, mix, intervals)", k19 == k20, json.dumps(k20, ensure_ascii=False))
        check("A7", "2,785 word cards / 393 Word Families / 60 SAT passages present", k20["words"] == 2785 and k20["fams"] == 393 and k20["passages"] == 60,
              f"words={k20['words']} fams={k20['fams']} passages={k20['passages']}")
        check("A7", "SAT mission mix 5:3:2 (s:c:t) unchanged", '"S":[["s",5,3],["c",3,1],["t",2,2]]' in k20["mix"], k20["mix"])
        same_fn = c19.js("()=>[startMission,finish,planMix,mixReviews,balanceMix,pickNew,dueList,chooseSentences,relQ,startPassages,pasAnswer,diagNext,diagSave,diagItems,diagStartLevel,hatch,backupText].map(f=>f.toString()).join('\\n')") == \
                  c20.js("()=>[startMission,finish,planMix,mixReviews,balanceMix,pickNew,dueList,chooseSentences,relQ,startPassages,pasAnswer,diagNext,diagSave,diagItems,diagStartLevel,hatch,backupText].map(f=>f.toString()).join('\\n')")
        check("A11", "learning engine source unchanged (mission, review schedule, passages, placement scoring, rewards, backup)", same_fn)
        c19.close(); c20.close()

        legacy = make_legacy(browser)
        L = json.loads(legacy)
        check("setup", "legacy data built: 2 students with words, history, coins, pets, diag, basics, pas",
              all(L["profiles"][k]["words"] for k in "ab") and L["profiles"]["a"].get("diag") and L["profiles"]["b"].get("pas") and L["profiles"]["a"]["pets"],
              {k: {f: (len(v) if isinstance(v, (dict, list)) else v) for f, v in L["profiles"][k].items() if f in ("words", "hist", "pets", "days", "coins", "xp", "stage", "diag", "basics", "pas")} for k in "ab"})
        open(SHOTS + "legacy_data.json", "w").write(legacy)

        # mission built from the same saved data with the same random numbers must be identical in v11.19 and v11.20
        sig = {}
        for ver in ("v1119", "v1120"):
            x = App(browser, ver, seed=99, storage=legacy); sig[ver] = (x.js(MISSION_SIG, "a"), ); x.close()
            x = App(browser, ver, seed=99, storage=legacy); sig[ver] += (x.js(MISSION_SIG, "b"), ); x.close()
        check("A7", "Today's Mission for existing students identical to v11.19 (same words, reviews, question types, sentences)", sig["v1119"] == sig["v1120"],
              f"a: {len(json.loads(sig['v1120'][0])['q'])} questions, b: {len(json.loads(sig['v1120'][1])['q'])} questions")

        # ============ A1: brand-new browser ============
        n = App(browser, "v1120")
        t = n.text()
        check("A1", "new browser shows Welcome, 0 students, no 막내/셋째",
              "Start Learning" in t and "Restore Progress" in t and n.js("Object.keys(S.profiles).length") == 0 and "막내" not in (n.stored() or "") and "셋째" not in (n.stored() or "") and "막내" not in t)
        n.shot("01_welcome_mobile")
        # ============ A2: sign-up validation ============
        n.click("Start Learning ▶")
        n.click("Continue ▶")
        check("A2", "empty nickname refused", "Please type a nickname" in n.text() and n.js("Object.keys(S.profiles).length") == 0)
        n.page.fill("#ns_name", "   ")
        n.click("Continue ▶")
        check("A2", "spaces-only nickname refused", "Please type a nickname" in n.text())
        n.page.fill("#ns_name", "Mina")
        n.click("Continue ▶")
        check("A2", "missing grade refused", "Please choose a grade from 4 to 12" in n.text() and n.js("Object.keys(S.profiles).length") == 0)
        n.shot("02_new_student_error")
        bad = n.js("()=>{ NS.name='X'; NS.grade=13; nsCreate(); const r1=Object.keys(S.profiles).length; NS.grade=3; nsCreate(); return [r1,Object.keys(S.profiles).length]; }")
        check("A2", "grade outside 4–12 refused (13, 3)", bad == [0, 0], bad)
        n.page.fill("#ns_name", "Mina")
        n.click("Back") if False else None
        n.reload()
        check("A2", "refresh before Continue creates no student", n.js("Object.keys(S.profiles).length") == 0 and "Start Learning" in n.text())
        n.close()

        # ============ main multi-student browser: 2 legacy students + 4 new ============
        m = App(browser, "v1120", seed=5, storage=legacy)
        before = json.loads(legacy)
        t = m.text()
        check("B", "existing students listed with their names; no Welcome screen", "Who's learning today?" in t and before["profiles"]["a"]["name"] in t and before["profiles"]["b"]["name"] in t and "Start Learning" not in t)
        m.shot("03_profiles_existing")
        check("A4", "loading v11.20 does not change existing data (stored text identical)", json.loads(m.stored())["profiles"] == before["profiles"])

        new_ids = {}
        plan = [("Alex", 4, 5), ("Jordan", 7, 8), ("Sam", 10, 10), ("Alex", 12, 3)]
        for i, (nm, gr, dl) in enumerate(plan):
            m.click("➕ Add Student")
            if i == 0: m.shot("04_new_student_form")
            ui_new_student(m, nm, gr, dl)
            pid = m.js("S.active")
            new_ids[(nm, gr)] = pid
            if i == 0: m.shot("05_placement_intro")
            p = m.js("P()")
            check("A2", f"{nm} grade {gr}: created with own ID, grade text, daily {dl}, temporary start stage",
                  pid.startswith("p_") and p["grade"] == f"{gr}th grade" and p["daily"] == dl and p["stage"] == ("m" if gr >= 7 else "e") and p["onboarding"]["step"] == "placement", f"id={pid} stage={p['stage']}")
            if gr == 7:            # refresh in the middle of sign-up (after Continue): resume placement step
                m.reload()
                t = m.text()
                check("A2", "refresh after Continue resumes the placement step", "Find your starting point" in t, t[:60])
            if gr == 4:            # take the placement check through the screen
                m.click("Take the Placement Check ▶"); m.click("Start ▶")
                m.shot("06_placement_question")
                do_diag(m, [8, 3])      # Elementary 8/8 → Middle tried: 3/8 → suggest Elementary
                m.shot("07_placement_result")
                d = m.js("P().diag")
                check("A6", "grade 4 check: E 8/8, M 3/8 → suggests Elementary", d["scores"] == {"e": 8, "m": 3} and d["suggested"] == "e", d["scores"])
                m.click("Use This Level")
            elif gr == 7:
                m.click("Take the Placement Check ▶"); m.click("Start ▶")
                do_diag(m, [7, 7, 6])   # starts at Middle: M 7 → H 7 → S 6 → suggest High School
                d = m.js("P().diag")
                check("A6", "grade 7 check: M 7/8, H 7/8, S 6/8 → suggests High School (7 = pass, 6 = not)", d["scores"] == {"m": 7, "h": 7, "s": 6} and d["suggested"] == "h", d["scores"])
                m.click("Choose Another Level")
                m.shot("08_choose_another_level")
                m.page.locator("#dgo button", has_text="Middle School").click()
                check("A6", "Choose Another Level → Middle School chosen instead of suggestion", m.js("P().stage") == "m" and m.js("P().diag.chosen") == "m")
            elif gr == 10:
                m.click("Start with the suggested level (🔥 Middle School)")
                check("A5", "grade 10 skip → Middle School (temporary), not SAT/High", m.js("P().stage") == "m" and m.js("P().onboarding.placement") == "skipped")
                m.shot("09_home_new_student_skipped")
                check("C", "home shows the temporary-level hint with a placement link", "Starting level based on grade only" in m.text())
            else:   # grade 12 Alex #2: check with 0 correct at every level
                m.click("Take the Placement Check ▶"); m.click("Start ▶")
                do_diag(m, [0, 0])     # starts at Middle: 0 → Elementary 0 → suggest Elementary
                d = m.js("P().diag")
                check("A6", "grade 12 check, all 'I don't know': M 0/8, E 0/8 → suggests Elementary", d["scores"] == {"m": 0, "e": 0} and d["suggested"] == "e", d["scores"])
                m.click("Use This Level")
            t = m.text()
            check("8", f"{nm} g{gr}: personal home with Today's Mission first", "Today's Mission" in t and t.find("Today's Mission") < t.find("Word Island"))
            m.click("◀ 👥")

        # A6 boundary: 8/8 at every level → SAT
        m.js("()=>{ const k=Object.keys(S.profiles).find(x=>S.profiles[x].grade==='12th grade'); }")
        ids = list(m.js("Object.keys(S.profiles)"))
        check("A3", "6 students in one browser (2 existing + 4 new), all IDs different", len(ids) == 6 and len(set(ids)) == 6, ids)
        alexes = [k for k in ids if m.js(f"S.profiles['{k}'].name") == "Alex"]
        check("A3", "two students named Alex kept apart by ID", len(alexes) == 2 and alexes[0] != alexes[1], alexes)
        m.shot("10_profiles_six_students")
        # placement taken later from home by the student who skipped (grade 10, Sam): 8/8, 8/8, 8/8 → SAT Prep
        sam = new_ids[("Sam", 10)]
        m.js(f"choose('{sam}')")
        words_before = m.js("JSON.stringify([P().words,P().hist||{},P().coins,P().pets,P().days])")
        m.page.get_by_role("button", name="🧭 Take the placement check").click()
        m.click("Start ▶")
        do_diag(m, [8, 8, 8])
        d = m.js("P().diag")
        check("A6", "later check from home: M 8, H 8, S 8 → suggests SAT Prep", d["scores"] == {"m": 8, "h": 8, "s": 8} and d["suggested"] == "s", d["scores"])
        m.click("Use This Level")
        check("A6", "placement does not change words, history, coins, pets, days", m.js("JSON.stringify([P().words,P().hist||{},P().coins,P().pets,P().days])") == words_before)
        check("A6", "after placement the hint disappears and stage = s", "Starting level based on grade only" not in m.text() and m.js("P().stage") == "s")

        # A7: Start Mission works for a new student and records the result
        jor = new_ids[("Jordan", 7)]
        m.js(f"choose('{jor}')")
        m.click("Start mission ▶")
        m.shot("11_new_student_mission_learn")
        sim = m.js("()=>{ M.all.forEach((id,i)=>M.ok[id]=i%3!==0); M.coins=80; finish(); const p=P(); return {words:Object.keys(p.words).length, coins:p.coins, days:Object.keys(p.days).length, due:Object.values(p.words).every(r=>r.due>today()-1)}; }")
        check("A7", "new student: Start Mission opens the lesson and finishing records words, coins, day", sim["words"] > 0 and sim["coins"] >= 80 and sim["days"] == 1, sim)
        m.shot("12_mission_clear")
        m.js("screenHome()")
        m.shot("13_home_after_mission")

        # existing student: open, home, settings save, switch — data must stay byte-identical
        m.js("screenProfiles()"); m.click("⚙️ Settings")
        m.shot("14_settings")
        sel = m.js("()=>['a','b'].map(k=>$('g_'+k).value)")
        m.click("◀ Save")
        m.js("choose('a')"); m.js("screenProfiles()"); m.js("choose('b')"); m.js("screenHome()"); m.click("◀ 👥")
        after = json.loads(m.stored())
        check("A4", "existing a/b byte-identical after home, settings save, switching, 4 sign-ups, placements and a mission",
              json.dumps(after["profiles"]["a"], ensure_ascii=False) == json.dumps(before["profiles"]["a"], ensure_ascii=False) and
              json.dumps(after["profiles"]["b"], ensure_ascii=False) == json.dumps(before["profiles"]["b"], ensure_ascii=False), f"grade selects={sel}")
        check("A4", "existing reward message and backup date kept", after["reward"] == before["reward"] and after.get("lastBackup") == before.get("lastBackup"))
        # rename in settings (by ID): rename second Alex only
        m.click("⚙️ Settings")
        m.page.fill(f"#n_{alexes[1]}", "Alex K")
        m.page.select_option(f"#g_{alexes[1]}", "11")
        m.click("◀ Save")
        st = json.loads(m.stored())["profiles"]
        check("A3", "rename and grade change apply to that ID only", st[alexes[1]]["name"] == "Alex K" and st[alexes[1]]["grade"] == "11th grade" and st[alexes[0]]["name"] == "Alex" and st[alexes[0]]["grade"] == "4th grade")

        # ============ A9 / A8: backup with 6 students, restore into a new browser ============
        backup = m.js("backupText()")
        m.close()
        r = App(browser, "v1120")
        r.click("📂 Restore Progress"); r.click("⌨️ Restore from code")
        r.page.fill("#rcode", backup); r.click("Restore", exact=True); r.page.click("#rgo")
        got = json.loads(r.stored())
        check("A8", "Restore Progress on first visit: v11.20 backup with 6 students restored", len(got["profiles"]) == 6 and got["profiles"] == json.loads(backup)["data"]["profiles"])
        r.close()
        r = App(browser, "v1120")
        r.click("📂 Restore Progress"); r.click("⌨️ Restore from code")
        v18_backup = json.dumps({"app": "wordquest", "v": "11.18", "saved": "2026-11-10T00:00:00Z", "data": json.loads(legacy)})
        r.page.fill("#rcode", v18_backup); r.click("Restore", exact=True); r.page.click("#rgo")
        check("A8", "older backup (v11.18/v11.19 format) restored on first visit", json.loads(r.stored())["profiles"] == json.loads(legacy)["profiles"])
        r.close()
        r = App(browser, "v1120")
        r.click("📂 Restore Progress"); r.click("⌨️ Restore from code")
        r.page.fill("#rcode", '{"hello":1}'); r.click("Restore", exact=True)
        check("A9", "invalid backup code refused, nothing saved", "doesn't look like a Word Quest backup" in r.text() and json.loads(r.stored())["profiles"] == {})
        r.close()

        # ============ A9: damaged saved data ============
        bad = legacy[: len(legacy) // 2]
        c = App(browser, "v1120", storage=bad)
        check("A9", "damaged saved data → recovery screen, nothing overwritten", "could not be read" in c.text() and c.stored() == bad)
        c.shot("15_recovery_screen")
        c.js("()=>{ try{ S.profiles.x={name:'t'}; save(); }catch(e){} }")
        check("A9", "save() refuses to write while data is unreadable", c.stored() == bad)
        c.click("⌨️ Restore from code"); c.page.fill("#rcode", backup); c.click("Restore", exact=True); c.page.click("#rgo")
        keys = c.js("Object.keys(localStorage)")
        kept = [k for k in keys if k.startswith("wordquest_v1_unreadable_")]
        check("A9", "restore from recovery screen works and keeps a copy of the damaged data", len(json.loads(c.stored())["profiles"]) == 6 and kept and c.js(f"localStorage.getItem('{kept[0]}')") == bad)
        c.close()
        c = App(browser, "v1120", storage="{not json")
        c.click("🗑️ Start over"); c.page.locator("#bkmsg button", has_text="Start over").click()
        check("A9", "Start over after confirmation → Welcome, copy kept", "Start Learning" in c.text() and any(k.startswith("wordquest_v1_unreadable_") for k in c.js("Object.keys(localStorage)")))
        c.close()

        # ============ A9: storage failure is shown ============
        f = App(browser, "v1120", storage=legacy)
        f.js("()=>{ Storage.prototype.setItem=function(){ throw new Error('QuotaExceededError'); }; choose('a'); }")
        check("A9", "failed save shows a warning on screen", "did not save the latest progress" in f.text())
        f.shot("16_save_failed_banner")
        f.close()

        # ============ A9: refresh during placement keeps records ============
        g = App(browser, "v1120", storage=legacy)
        g.js("()=>{ diagStart('a'); diagAnswer(true); diagAnswer(false); }")
        g.reload()
        check("A9", "refresh in the middle of a placement check: data unchanged", json.loads(g.stored())["profiles"] == json.loads(legacy)["profiles"])
        g.close()

        # ============ A10: v11.20 backup opened in v11.18, then back in v11.20 ============
        o = App(browser, "v1118")
        o.js("()=>{ restoreCodeUI(); }") if False else None
        o.js("(t)=>{ document.body.insertAdjacentHTML('beforeend','<div id=\"bkmsg\"></div>'); restoreText(t); $('rgo').click(); }", backup)
        t18 = o.text()
        names18 = [o.js(f"S.profiles['{k}'].name") for k in o.js("Object.keys(S.profiles)")]
        err = None
        try:
            for k in o.js("Object.keys(S.profiles)"):
                o.js(f"()=>{{ choose('{k}'); screenHome(); startMission(); screenHome(); }}")
        except Exception as e:
            err = str(e)
        check("A10", "v11.18 opens a v11.20 backup: 6 students listed, home and mission start for each, no errors",
              len(names18) == 6 and err is None and not o.errors, f"errors={o.errors[:2]} {err}")
        o.shot("17_v1118_reads_v1120_backup")
        back = o.js("backupText()")
        o.close()
        q = App(browser, "v1120")
        q.js("(t)=>{ screenRestore(); restoreText(t); $('rgo').click(); }", back)
        ok = len(q.js("Object.keys(S.profiles)")) == 6 and q.js("Object.values(S.profiles).filter(p=>p.onboarding).length") == 4
        check("A10", "backup saved again by v11.18 reads back into v11.20 (onboarding info kept)", ok)
        q.close()

        # ============ A12: screen sizes ============
        for (w, h, tag, mob) in [(375, 812, "375_mobile", True), (420, 900, "420_mobile", True), (820, 1180, "820_tablet", True), (1280, 900, "1280_desktop", False)]:
            v = App(browser, "v1120", width=w, height=h, mobile=mob, storage=backup and json.dumps(json.loads(backup)["data"]))
            v.js(f"choose('{new_ids[('Jordan', 7)]}')")
            over = v.js("document.documentElement.scrollWidth > window.innerWidth + 1")
            v.shot(f"18_home_{tag}")
            v.js("screenProfiles()"); v.shot(f"19_profiles_{tag}")
            check("A12", f"{tag}: no sideways scrolling on home", not over)
            v.close()
            v = App(browser, "v1120", width=w, height=h, mobile=mob)
            v.click("Start Learning ▶")
            over = v.js("document.documentElement.scrollWidth > window.innerWidth + 1")
            v.shot(f"20_signup_{tag}")
            check("A12", f"{tag}: no sideways scrolling on sign-up", not over)
            v.close()

        browser.close()
    check("all", "no JavaScript errors in any page", not PAGE_ERRORS, PAGE_ERRORS[:3])

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        RESULTS.append(("crash", traceback.format_exc().splitlines()[-1], False, ""))
    json.dump(RESULTS, open(SHOTS + "results.json", "w"), ensure_ascii=False, indent=1)
    print(f"\n{sum(r[2] for r in RESULTS)}/{len(RESULTS)} passed")
