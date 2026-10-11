"""
FocusFlow-style AI planner  |  dark + purple
Run:  streamlit run app.py
AI features need an ANTHROPIC_API_KEY env variable (everything else works without it).
"""
import json
import os
import time
import uuid
from datetime import date, datetime, timedelta

import plotly.graph_objects as go
import streamlit as st

# ----------------------------- config -----------------------------
NAME = "K"                       # change me
FOCUS_MIN = 25                   # pomodoro length (minutes)
DAILY_TASK_GOAL = 3
DAILY_FOCUS_GOAL_MIN = 120
WATER_GOAL = 8
EXERCISE_GOAL_MIN = 30
MODEL = "claude-sonnet-5-5"
DATA_FILE = "planner_data.json"

BG = "#0e0a1a"
CARD = "#17112b"
BORDER = "#2a2147"
TEXT = "#ece8f9"
MUTED = "#9a91b8"
PURPLE = "#8b5cf6"
PURPLE_SOFT = "rgba(139,92,246,0.25)"
TAGS = {  # tag: (text colour, bg colour)
    "Personal": ("#c4b5fd", "rgba(139,92,246,.15)"),
    "Work": ("#93c5fd", "rgba(59,130,246,.15)"),
    "Health": ("#fdba74", "rgba(249,115,22,.15)"),
    "Learning": ("#86efac", "rgba(34,197,94,.15)"),
}

st.set_page_config(page_title="FocusFlow AI", page_icon="🟣", layout="wide")

# ----------------------------- styling -----------------------------
st.markdown(
    f"""
<style>
#MainMenu, footer, header {{visibility: hidden;}}
.stApp {{background: {BG}; color: {TEXT};}}
.block-container {{padding-top: 1.6rem; max-width: 1250px;}}
section[data-testid="stSidebar"] {{background: {CARD}; border-right: 1px solid {BORDER};}}
h1,h2,h3,h4,p,label,span,div {{color: {TEXT};}}
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px;
}}
.card-title {{font-weight: 600; font-size: 0.95rem; margin-bottom: .4rem;}}
.stat {{background:{CARD}; border:1px solid {BORDER}; border-radius:14px; padding:16px 18px;
        display:flex; justify-content:space-between; align-items:center;}}
.stat .l {{color:{MUTED}; font-size:.78rem;}}
.stat .v {{font-size:1.5rem; font-weight:700; margin:2px 0;}}
.stat .s {{color:{MUTED}; font-size:.75rem;}}
.stat .i {{width:42px; height:42px; border-radius:50%; display:flex; align-items:center;
          justify-content:center; font-size:1.2rem; background:{PURPLE_SOFT};}}
.pill {{font-size:.68rem; padding:2px 8px; border-radius:6px; margin-left:6px;}}
.bar {{background:#261d45; border-radius:99px; height:6px; margin:4px 0 12px;}}
.bar > div {{background:{PURPLE}; height:6px; border-radius:99px;}}
.goal-row {{display:flex; justify-content:space-between; font-size:.85rem;}}
.banner {{background:{CARD}; border:1px solid {BORDER}; border-radius:14px; padding:14px 18px;}}
button[kind="primary"] {{background:{PURPLE}; border:none; color:white; border-radius:10px;}}
button[kind="primary"]:hover {{background:#7c3aed; color:white;}}
button[kind="secondary"] {{background:transparent; border:1px solid {BORDER}; color:{TEXT}; border-radius:10px;}}
div[data-baseweb="input"], div[data-baseweb="select"] > div, textarea {{
    background:#120c24 !important; border-color:{BORDER} !important; color:{TEXT} !important;}}
.ring-wrap {{display:flex; justify-content:center; padding:6px 0;}}
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------- data layer -----------------------------
def iso(d: date) -> str:
    return d.isoformat()


def seed_data() -> dict:
    today = date.today()
    tasks = [
        {"id": uuid.uuid4().hex[:8], "title": "Read 20 pages", "tag": "Personal", "time": "09:00",
         "date": iso(today), "done": False, "done_on": None},
        {"id": uuid.uuid4().hex[:8], "title": "Build project landing page", "tag": "Work", "time": "11:00",
         "date": iso(today), "done": False, "done_on": None},
        {"id": uuid.uuid4().hex[:8], "title": "Workout", "tag": "Health", "time": "16:00",
         "date": iso(today), "done": False, "done_on": None},
        {"id": uuid.uuid4().hex[:8], "title": "Learn TypeScript", "tag": "Learning", "time": "18:00",
         "date": iso(today), "done": False, "done_on": None},
        {"id": uuid.uuid4().hex[:8], "title": "Plan tomorrow", "tag": "Personal", "time": "21:00",
         "date": iso(today), "done": False, "done_on": None},
        {"id": uuid.uuid4().hex[:8], "title": "Project meeting", "tag": "Work", "time": "10:00",
         "date": iso(today + timedelta(days=1)), "done": False, "done_on": None},
        {"id": uuid.uuid4().hex[:8], "title": "Study algorithms", "tag": "Learning", "time": "09:00",
         "date": iso(today + timedelta(days=2)), "done": False, "done_on": None},
    ]
    # demo history so the charts/streak aren't empty on first launch
    focus, done_counts = {}, [3, 5, 2, 4, 1, 3]
    focus_mins = [150, 200, 95, 160, 120, 170]
    for i in range(1, 7):
        d = today - timedelta(days=i)
        focus[iso(d)] = focus_mins[i - 1]
        for _ in range(done_counts[i - 1]):
            tasks.append({"id": uuid.uuid4().hex[:8], "title": "Past task", "tag": "Personal",
                          "time": "12:00", "date": iso(d), "done": True, "done_on": iso(d)})
    return {"tasks": tasks, "focus": focus, "water": {}, "exercise": {}}


def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return seed_data()


def save():
    with open(DATA_FILE, "w") as f:
        json.dump(st.session_state.data, f, indent=2)


if "data" not in st.session_state:
    st.session_state.data = load_data()
    save()
if "timer" not in st.session_state:
    st.session_state.timer = {"running": False, "end": 0.0, "remaining": FOCUS_MIN * 60}
if "ai_plan" not in st.session_state:
    st.session_state.ai_plan = []

D = st.session_state.data
TODAY = iso(date.today())


def fmt_time(t: str) -> str:
    return datetime.strptime(t, "%H:%M").strftime("%I:%M %p").lstrip("0")


def today_tasks():
    return sorted([t for t in D["tasks"] if t["date"] == TODAY], key=lambda t: t["time"])


def upcoming_tasks():
    return sorted([t for t in D["tasks"] if t["date"] > TODAY and not t["done"]],
                  key=lambda t: (t["date"], t["time"]))[:4]


def tasks_done_today() -> int:
    return sum(1 for t in D["tasks"] if t["done_on"] == TODAY)


def focus_today() -> int:
    return D["focus"].get(TODAY, 0)


def streak() -> int:
    n, d = 0, date.today()
    if D["focus"].get(iso(d), 0) == 0:
        d -= timedelta(days=1)  # today not started yet shouldn't break the streak
    while D["focus"].get(iso(d), 0) > 0:
        n += 1
        d -= timedelta(days=1)
    return n


def hm(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"


def add_task(title, tag, time_str, day: date):
    D["tasks"].append({"id": uuid.uuid4().hex[:8], "title": title, "tag": tag, "time": time_str,
                       "date": iso(day), "done": False, "done_on": None})
    save()


def toggle_task(tid: str):
    for t in D["tasks"]:
        if t["id"] == tid:
            t["done"] = st.session_state[f"chk_{tid}"]
            t["done_on"] = TODAY if t["done"] else None
    save()


def delete_task(tid: str):
    D["tasks"] = [t for t in D["tasks"] if t["id"] != tid]
    save()


def bump(key: str, amount: int):
    D[key][TODAY] = D[key].get(TODAY, 0) + amount
    save()


# ----------------------------- AI layer -----------------------------
def ask_claude(system: str, user: str, max_tokens: int = 1000):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None, "Set the ANTHROPIC_API_KEY environment variable to use AI features."
    try:
        from anthropic import Anthropic
        msg = Anthropic(api_key=key).messages.create(
            model=MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text, None
    except Exception as e:  # network, auth, etc.
        return None, f"AI request failed: {e}"


def ai_schedule(brain_dump: str):
    system = (
        "You are a planning assistant. Turn the user's brain dump into a realistic schedule for today. "
        "Reply with ONLY a JSON array, no prose, no code fences. Each item: "
        '{"title": str, "tag": one of ["Personal","Work","Health","Learning"], "time": "HH:MM" 24h}. '
        "Space tasks out, put hard focus work earlier in the day, include breaks only if asked."
    )
    existing = ", ".join(f"{t['title']} at {t['time']}" for t in today_tasks()) or "nothing yet"
    text, err = ask_claude(system, f"Already planned today: {existing}\n\nBrain dump:\n{brain_dump}")
    if err:
        return [], err
    try:
        clean = text.replace("```json", "").replace("```", "").strip()
        items = json.loads(clean)
        return [i for i in items if i.get("tag") in TAGS and len(i.get("time", "")) == 5], None
    except Exception:
        return [], "Couldn't read the AI's answer. Try rephrasing your plan."


def ai_tip():
    system = "You are a friendly, concise productivity coach. Reply in 1-2 short sentences."
    summary = (f"Tasks done today: {tasks_done_today()}/{len(today_tasks())}. "
               f"Focus today: {focus_today()} min. Streak: {streak()} days.")
    return ask_claude(system, summary, max_tokens=150)


# ----------------------------- UI helpers -----------------------------
def stat_card(label, value, sub, icon):
    st.markdown(
        f'<div class="stat"><div><div class="l">{label}</div><div class="v">{value}</div>'
        f'<div class="s">{sub}</div></div><div class="i">{icon}</div></div>',
        unsafe_allow_html=True,
    )


def tag_pill(tag):
    fg, bg = TAGS.get(tag, TAGS["Personal"])
    return f'<span class="pill" style="color:{fg};background:{bg}">{tag}</span>'


def goal_bar(label, cur, target, unit_fmt=lambda x: str(x)):
    pct = min(100, int(cur / target * 100)) if target else 0
    st.markdown(
        f'<div class="goal-row"><span>{label}</span><span style="color:{MUTED}">'
        f"{unit_fmt(cur)} / {unit_fmt(target)}</span></div>"
        f'<div class="bar"><div style="width:{pct}%"></div></div>',
        unsafe_allow_html=True,
    )


def style_fig(fig, height=210):
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=MUTED, size=11),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(gridcolor=BORDER, zeroline=False),
    )
    return fig


def week_days():
    start = date.today() - timedelta(days=date.today().weekday())
    return [start + timedelta(days=i) for i in range(7)]


# ----------------------------- focus timer -----------------------------
def toggle_timer():
    t = st.session_state.timer
    if t["running"]:
        t["remaining"] = max(0, t["end"] - time.time())
        t["running"] = False
    else:
        t["end"] = time.time() + t["remaining"]
        t["running"] = True


def reset_timer():
    st.session_state.timer = {"running": False, "end": 0.0, "remaining": FOCUS_MIN * 60}


@st.fragment(run_every=1)
def timer_widget(where: str):
    t = st.session_state.timer
    remaining = max(0, t["end"] - time.time()) if t["running"] else t["remaining"]

    if t["running"] and remaining <= 0:  # session finished
        bump("focus", FOCUS_MIN)
        reset_timer()
        st.toast("Focus session complete 🎉")
        st.rerun()

    total = FOCUS_MIN * 60
    circ = 2 * 3.14159 * 70
    offset = circ * (1 - (total - remaining) / total)
    mm, ss = divmod(int(remaining), 60)
    st.markdown(
        f"""<div class="ring-wrap"><svg width="190" height="190" viewBox="0 0 190 190">
        <circle cx="95" cy="95" r="70" fill="none" stroke="#261d45" stroke-width="9"/>
        <circle cx="95" cy="95" r="70" fill="none" stroke="{PURPLE}" stroke-width="9" stroke-linecap="round"
          stroke-dasharray="{circ:.1f}" stroke-dashoffset="{offset:.1f}" transform="rotate(-90 95 95)"/>
        <text x="95" y="86" text-anchor="middle" fill="{MUTED}" font-size="12">Pomodoro</text>
        <text x="95" y="116" text-anchor="middle" fill="{TEXT}" font-size="34" font-weight="600">{mm:02d}:{ss:02d}</text>
        </svg></div>""",
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([3, 1])
    c1.button("Pause" if t["running"] else "Start", on_click=toggle_timer, type="primary",
              use_container_width=True, key=f"tbtn_{where}")
    c2.button("↺", on_click=reset_timer, use_container_width=True, key=f"trst_{where}")


# ----------------------------- sidebar -----------------------------
with st.sidebar:
    st.markdown(f'<h3 style="margin:0 0 14px">🟣 FocusFlow <span style="color:{PURPLE}">AI</span></h3>',
                unsafe_allow_html=True)
    page = st.radio("nav", ["🏠 Dashboard", "✅ Tasks", "⏱ Focus Timer", "✨ AI Planner"],
                    label_visibility="collapsed")
    st.markdown("<br>" * 6, unsafe_allow_html=True)
    st.caption("You've got this! Small steps every day lead to big results.")

# ----------------------------- header -----------------------------
hour = datetime.now().hour
greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
h1, h2 = st.columns([4, 1])
h1.markdown(f"## {greet}, {NAME}! 👋")
h1.caption("Let's make today productive.")
h2.markdown(f'<p style="text-align:right;color:{MUTED};font-size:.8rem;padding-top:10px">'
            f"{datetime.now().strftime('%A, %B %d, %Y')}</p>", unsafe_allow_html=True)


# ----------------------------- pages -----------------------------
def add_task_form(key: str):
    with st.expander("＋ Add new task"):
        with st.form(key, clear_on_submit=True):
            title = st.text_input("Task")
            c1, c2, c3 = st.columns(3)
            tag = c1.selectbox("Tag", list(TAGS))
            tm = c2.time_input("Time", value=datetime.strptime("09:00", "%H:%M").time())
            day = c3.date_input("Date", value=date.today())
            if st.form_submit_button("Add task", type="primary") and title.strip():
                add_task(title.strip(), tag, tm.strftime("%H:%M"), day)
                st.rerun()


def page_dashboard():
    done_goal_pct = int(min(100, (tasks_done_today() / DAILY_TASK_GOAL) * 100))
    c = st.columns(4)
    with c[0]:
        stat_card("Tasks Completed", tasks_done_today(), "today", "✅")
    with c[1]:
        stat_card("Focus Time", hm(focus_today()), "today", "⏱")
    with c[2]:
        stat_card("Current Streak", f"{streak()} days", "Keep it up!", "🔥")
    with c[3]:
        stat_card("Daily Goal", f"{done_goal_pct}%", "Almost there!" if done_goal_pct < 100 else "Done!", "🎯")

    st.write("")
    a, b, g = st.columns(3)

    with a, st.container(border=True):
        st.markdown('<div class="card-title">Today\'s Tasks</div>', unsafe_allow_html=True)
        tasks = today_tasks()
        if not tasks:
            st.caption("Nothing planned yet. Add a task or ask the AI Planner.")
        for t in tasks:
            st.checkbox(f"{t['title']}  ·  {t['tag']}  ·  {fmt_time(t['time'])}", value=t["done"],
                        key=f"chk_{t['id']}", on_change=toggle_task, args=(t["id"],))
        add_task_form("add_dash")

    with b, st.container(border=True):
        st.markdown('<div class="card-title">Focus Timer</div>', unsafe_allow_html=True)
        timer_widget("dash")

    with g, st.container(border=True):
        st.markdown('<div class="card-title">Daily Goals</div>', unsafe_allow_html=True)
        goal_bar("Complete tasks", tasks_done_today(), DAILY_TASK_GOAL)
        goal_bar("Focus for 2+ hours", focus_today(), DAILY_FOCUS_GOAL_MIN, hm)
        goal_bar("Drink 8 glasses of water", D["water"].get(TODAY, 0), WATER_GOAL)
        goal_bar("Exercise for 30 minutes", D["exercise"].get(TODAY, 0), EXERCISE_GOAL_MIN)
        w, e = st.columns(2)
        w.button("+1 water", on_click=bump, args=("water", 1), use_container_width=True)
        e.button("+10 min", on_click=bump, args=("exercise", 10), use_container_width=True)

    st.write("")
    p, u, wk = st.columns(3)
    days = week_days()
    labels = [d.strftime("%a") for d in days]

    with p, st.container(border=True):
        st.markdown('<div class="card-title">Productivity Overview</div>', unsafe_allow_html=True)
        counts = [sum(1 for t in D["tasks"] if t["done_on"] == iso(d)) for d in days]
        fig = go.Figure(go.Scatter(x=labels, y=counts, mode="lines+markers", fill="tozeroy",
                                   line=dict(color=PURPLE, width=3, shape="spline"),
                                   fillcolor=PURPLE_SOFT, marker=dict(size=7, color=BG,
                                   line=dict(color=PURPLE, width=2))))
        st.plotly_chart(style_fig(fig), use_container_width=True, config={"displayModeBar": False})
        st.caption("Tasks completed per day")

    with u, st.container(border=True):
        st.markdown('<div class="card-title">Upcoming Tasks</div>', unsafe_allow_html=True)
        ups = upcoming_tasks()
        if not ups:
            st.caption("No upcoming tasks.")
        for t in ups:
            d = datetime.strptime(t["date"], "%Y-%m-%d").strftime("%a")
            st.markdown(f"○ **{t['title']}** {tag_pill(t['tag'])}<br>"
                        f'<span style="color:{MUTED};font-size:.75rem;margin-left:18px">'
                        f"{d}, {fmt_time(t['time'])}</span>", unsafe_allow_html=True)

    with wk, st.container(border=True):
        st.markdown('<div class="card-title">Weekly Focus</div>', unsafe_allow_html=True)
        mins = [D["focus"].get(iso(d), 0) for d in days]
        st.markdown(f'<div style="font-size:1.3rem;font-weight:700">{hm(sum(mins))}</div>'
                    f'<div style="color:{MUTED};font-size:.75rem">Total focus time</div>',
                    unsafe_allow_html=True)
        fig = go.Figure(go.Bar(x=labels, y=[m / 60 for m in mins], marker_color=PURPLE))
        st.plotly_chart(style_fig(fig, 170), use_container_width=True, config={"displayModeBar": False})

    st.write("")
    with st.container(border=True):
        l, r = st.columns([4, 1])
        tip = st.session_state.get("tip") or "Tap the button for a quick AI nudge based on your day."
        l.markdown(f"**Keep going, {NAME}! 💪**  \n{tip}")
        if r.button("Get AI tip", use_container_width=True):
            text, err = ai_tip()
            st.session_state.tip = text or err
            st.rerun()


def page_tasks():
    st.subheader("All tasks")
    add_task_form("add_tasks")
    for d in sorted({t["date"] for t in D["tasks"] if not t["done"] or t["date"] >= TODAY}, reverse=False):
        items = sorted([t for t in D["tasks"] if t["date"] == d], key=lambda t: t["time"])
        if d < TODAY and all(t["done"] for t in items):
            continue
        st.markdown(f"**{datetime.strptime(d, '%Y-%m-%d').strftime('%A, %b %d')}**")
        for t in items:
            c1, c2 = st.columns([8, 1])
            c1.checkbox(f"{t['title']}  ·  {t['tag']}  ·  {fmt_time(t['time'])}", value=t["done"],
                        key=f"chk_{t['id']}", on_change=toggle_task, args=(t["id"],))
            c2.button("🗑", key=f"del_{t['id']}", on_click=delete_task, args=(t["id"],))


def page_timer():
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid, st.container(border=True):
        st.markdown('<div class="card-title">Focus Timer</div>', unsafe_allow_html=True)
        timer_widget("page")
        st.caption(f"Focused today: {hm(focus_today())}")


def page_ai():
    st.subheader("AI Planner")
    st.caption("Dump everything on your mind. The AI turns it into a timed schedule you can accept.")
    dump = st.text_area("What do you need to get done today?", height=130,
                        placeholder="finish the SUSC slides, gym, revise algorithms for 2 hours, call mom...")
    if st.button("✨ Plan my day", type="primary") and dump.strip():
        with st.spinner("Thinking..."):
            plan, err = ai_schedule(dump)
        if err:
            st.error(err)
        else:
            st.session_state.ai_plan = plan

    if st.session_state.ai_plan:
        st.markdown("**Suggested schedule**")
        for item in sorted(st.session_state.ai_plan, key=lambda i: i["time"]):
            st.markdown(f"{fmt_time(item['time'])} — {item['title']} {tag_pill(item['tag'])}",
                        unsafe_allow_html=True)
        if st.button("Add all to today", type="primary"):
            for item in st.session_state.ai_plan:
                add_task(item["title"], item["tag"], item["time"], date.today())
            st.session_state.ai_plan = []
            st.toast("Added to today's tasks")
            st.rerun()


{"🏠 Dashboard": page_dashboard, "✅ Tasks": page_tasks,
 "⏱ Focus Timer": page_timer, "✨ AI Planner": page_ai}[page]()
