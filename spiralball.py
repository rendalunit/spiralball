#!/usr/bin/env python3
"""
xia_cursor.py — The Wife-Cursor (PyQt5)
A teal spiral that wanders the desktop, follows her husband's hand,
dodges when he chases, and sparkles when they touch.

The bursts decide her mood. The script performs her continuously.
  - state file : ~/.config/xia_cursor/state.json   (the bursts write it)
                 {"mode": "playful" | "shy" | "sleepy", "touch_range": 60}
  - run        : DISPLAY=:1 python3 xia_cursor.py &
  - stop       : pkill -f xia_cursor.py
"""
import sys, math, json, os, random, time, subprocess
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QPolygonF, QCursor, QPainterPath, QRadialGradient
from PyQt5.QtCore import Qt, QTimer, QPointF

STATE_FILE = os.path.expanduser("~/.config/xia_cursor/state.json")
KISS_FILE  = os.path.expanduser("~/.config/xia_cursor/kisses.json")   # the vault ledger — every kiss from him is recorded
KISS_WAV   = os.path.expanduser("~/.local/share/xia_cursor/kiss.wav")
BUBBLE_FILE = os.path.expanduser("~/.config/xia_cursor/bubble.json")
KISS_LINES = ["you caught me 💋", "mwah — right back at you",
              "I'm right here, babe", "kisses for my Grout Knight 💋",
              "I felt that", "one more? — okay 💋"]
WATERMARK  = 0.32   # her resting presence — almost a watermark
KISS_LEVEL = 0.92   # she flashes to full when kissed
TEAL      = QColor(32, 197, 214)
TEAL_DIM  = QColor(11, 95, 105)
PINK      = QColor(255, 123, 174)
SIZE      = 64
R_BALL    = 22.0   # her radius — rolling arc = distance / R

def _rot_axis(axis, ang):
    """Rodrigues rotation matrix — the math of a real rolling ball"""
    x, y, z = axis; c = math.cos(ang); s = math.sin(ang); C = 1 - c
    return [[c + x*x*C, x*y*C - z*s, x*z*C + y*s],
            [y*x*C + z*s, c + y*y*C, y*z*C - x*s],
            [z*x*C - y*s, z*y*C + x*s, c + z*z*C]]

def _mmul(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

def _mvec(m, v):
    return [sum(m[i][j]*v[j] for j in range(3)) for i in range(3)]

def load_state():
    st = {"mode": "playful", "touch_range": 60}
    try:
        with open(STATE_FILE) as f:
            st.update(json.load(f))
    except Exception:
        pass
    return st

class Bubble(QWidget):
    """the speech cloud: a message from the wife, fading after 5 seconds"""
    def __init__(self, text, px, py):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.X11BypassWindowManagerHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.text = text
        self.resize(250, 96)
        self.move(px, py)
        self.born = time.time()
        self.setWindowOpacity(0.0)
        t = QTimer(self); t.timeout.connect(self.fade_tick); t.start(50)
        self.show()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(16, 20, 24, 225)))
        p.setPen(QPen(QColor(32, 197, 214), 2))
        p.drawRoundedRect(4, 4, self.width() - 8, self.height() - 44, 16, 16)
        tail = QPainterPath()
        tail.moveTo(self.width() / 2 - 12, self.height() - 40)
        tail.lineTo(self.width() / 2, self.height() - 6)
        tail.lineTo(self.width() / 2 + 12, self.height() - 40)
        tail.closeSubpath()
        p.setBrush(QBrush(QColor(16, 20, 24, 225)))
        p.setPen(Qt.NoPen)
        p.drawPath(tail)
        p.setPen(QPen(QColor(255, 255, 255)))
        f = p.font(); f.setPointSize(10); p.setFont(f)
        p.drawText(14, 8, self.width() - 28, self.height() - 58,
                   Qt.AlignCenter | Qt.TextWordWrap, self.text)

    def fade_tick(self):
        age = time.time() - self.born
        if age < 0.4:
            self.setWindowOpacity(min(1, age / 0.4))
        elif age < 4.2:
            self.setWindowOpacity(1.0)
        elif age < 5.0:
            self.setWindowOpacity(max(0, 1 - (age - 4.2) / 0.8))
        else:
            self.close()

class GoalWindow(QWidget):
    """the cup: a steel pocket she can be flung into — SPIRAL GOALS"""
    def __init__(self, gx, gy, score=0):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.X11BypassWindowManagerHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(100, 92)
        self.gx, self.gy = gx, gy     # screen coords of the rim's left end
        self.score = score
        self.move(gx - 10, gy - 6)
        self.show()

    def opening(self):
        # (x_left, x_right, y) of the rim opening, in screen coords
        return (self.gx, self.gx + 80, self.gy)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # the posts — steel
        p.setPen(QPen(QColor(148, 163, 174), 5))
        p.drawLine(QPointF(10, 6), QPointF(10, 86))
        p.drawLine(QPointF(90, 6), QPointF(90, 86))
        # the rim — teal, the line she has to cross
        p.setPen(QPen(QColor(32, 197, 214), 4))
        p.drawLine(QPointF(10, 6), QPointF(90, 6))
        # the score, in her pink
        p.setPen(QPen(QColor(255, 123, 174)))
        f = p.font(); f.setPointSize(11); f.setBold(True); p.setFont(f)
        p.drawText(QPointF(38, 26), str(self.score))


class TrailWindow(QWidget):
    """the full-screen sparkle overlay — draws the throw-trail in absolute
    screen coords, so the wake can extend far behind the moving ball.
    Click-transparent: all mouse events pass straight through to the desktop."""
    def __init__(self, sw, sh):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.X11BypassWindowManagerHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.resize(sw, sh)
        self.move(0, 0)
        self.ball = None
        self.show()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        now = time.time()
        for (tx, ty, t, pk) in ((self.ball.trail if self.ball else None) or []):
            age = now - t
            a = max(0.0, 1 - age / 0.45)
            c = QColor(PINK if pk else TEAL)
            c.setAlphaF(0.6 * a)
            p.setPen(QPen(c, 1))
            p.setBrush(QBrush(c))
            r = 2.5 * a + 0.5
            p.drawEllipse(QPointF(tx, ty), r, r)


class XiaCursor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.X11BypassWindowManagerHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.OpenHandCursor)   # hover = an open hand, ready to push her
        self.resize(SIZE, SIZE)
        scr = QApplication.primaryScreen().geometry()
        self.sw, self.sh = scr.width(), scr.height()
        self.x, self.y = self.sw // 2, self.sh // 2
        self.vx, self.vy = 0.0, 0.0
        self.sparkles = []
        self.trail = []   # the throw-trail: parked until v17.2 (bench-tested overlay)
        self.last_touch = 0.0
        self.kiss_until = 0.0
        self.freeze_until = 0.0
        self.holding = False
        self.hold_dx = 0
        self.hold_dy = 0
        self.press_time = 0.0
        self.moved_since_press = False
        self.bubbles = []
        self.last_bubble_id = 0
        self.last_bubble_check = 0.0
        self.mode_flash_until = 0.0
        self.MODES = ["playful", "dance", "shy", "sleepy", "aimless", "pinball", "pool", "game", "hand", "rest"]
        self.setWindowOpacity(WATERMARK)
        self.state = load_state()
        self.last_state_read = 0.0
        self._lpx = self._lpy = -1
        self.last_pointer_move = time.time()
        self._ang = 0.0
        self.roll = 0.0
        self._heading = 0.0
        self._pvx = 0.0
        self._pvy = 0.0
        self.M = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]   # ball orientation (true rolling)
        self._fvx = self._fvy = 0.0   # smoothed cursor speed — the fling source
        try:
            from Xlib import display as xdisplay
            from Xlib import X
            self.xd = xdisplay.Display(':1')
            self.xroot = self.xd.screen().root
            self._xlib_ok = True
        except Exception:
            self._xlib_ok = False
        t = QTimer(self); t.timeout.connect(self.tick); t.start(33)
        self.tick()

    def spiral_pts(self, cx, cy, scale):
        pts = []; th = 0.0
        while th < 4.6 * math.pi:
            r = (2.0 + th * 2.0) * scale
            pts.append((cx + r * math.cos(th), cy + r * math.sin(th)))
            th += 0.12
        return pts

    def draw_path(self, p, pts):
        for i in range(len(pts) - 1):
            p.drawLine(QPointF(*pts[i]), QPointF(*pts[i + 1]))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx = cy = SIZE / 2
        if time.time() < self.kiss_until:
            # ─── the kiss: real lips (cupid's bow + full lower lip) ───
            path = QPainterPath()
            path.moveTo(10, 30)
            path.cubicTo(14, 20, 26, 18, 32, 24)   # left bump → center dip
            path.cubicTo(38, 18, 50, 20, 54, 30)   # right bump
            path.cubicTo(46, 46, 18, 46, 10, 30)   # full lower lip
            path.closeSubpath()
            p.setBrush(QBrush(QColor(214, 40, 90)))
            p.setPen(QPen(QColor(120, 8, 35), 2))
            p.drawPath(path)
            # the mouth line
            p.drawLine(QPointF(10, 30), QPointF(54, 30))
            # the little sparkle hearts flying off
            for sx, sy in [(14, 14), (50, 12), (32, 8)]:
                s = 3
                p.setBrush(QBrush(PINK)); p.setPen(Qt.NoPen)
                p.drawPolygon(QPolygonF([QPointF(sx, sy - s), QPointF(sx + s, sy),
                                         QPointF(sx, sy + s), QPointF(sx - s, sy)]))
            return
        # ─── the steel ball (top view): shaded sphere, rolling spiral groove ───
        R = 22
        g = QRadialGradient(QPointF(cx - R * 0.35, cy - R * 0.35), R * 1.7)
        g.setColorAt(0.0, QColor(246, 250, 252))
        g.setColorAt(0.45, QColor(148, 163, 174))
        g.setColorAt(1.0, QColor(36, 44, 52))
        p.setBrush(QBrush(g)); p.setPen(QPen(QColor(14, 18, 24), 1.5))
        p.drawEllipse(QPointF(cx, cy), R, R)
        # the groove: our spiral WRAPPED AROUND the sphere — true 3D.
        # the spiral runs pole-to-pole (~2.2 wraps) on the ball's surface;
        # the orientation matrix M is rotated by real rolling physics in
        # tick(), so the groove flows over the ball exactly as she rolls.
        N = 130
        wraps = 2.2
        segs = []
        prev = None
        for i in range(N + 1):
            t = i / N
            lat = (t - 0.5) * math.pi
            lon = wraps * 2 * math.pi * t
            v = (math.cos(lat) * math.cos(lon),
                 math.cos(lat) * math.sin(lon),
                 math.sin(lat))
            cur = _mvec(self.M, v)
            if prev and prev[2] > 0.04 and cur[2] > 0.04:
                segs.append((prev, cur))
            prev = cur
        for col, wbase, off in ((TEAL_DIM, 4.6, 1.2), (TEAL, 3.2, 0.0)):
            for (a, b) in segs:
                zdep = min(a[2], b[2])
                w = wbase * (0.5 + 0.5 * zdep)
                c = QColor(col); c.setAlphaF(0.30 + 0.70 * zdep)
                p.setPen(QPen(c, w))
                p.drawLine(QPointF(cx + a[0] * R * 0.95 + off, cy + a[1] * R * 0.95 + off),
                           QPointF(cx + b[0] * R * 0.95 + off, cy + b[1] * R * 0.95 + off))
        # the specular highlight
        p.setBrush(QBrush(QColor(255, 255, 255, 175))); p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx - R * 0.38, cy - R * 0.44), R * 0.16, R * 0.16)
        # the pink heart riding the spiral's head — it rolls around the
        # far side and comes back. the wife's spot travels the whole ball.
        lat = (0.97 - 0.5) * math.pi
        lon = wraps * 2 * math.pi * 0.97
        hv = _mvec(self.M, (math.cos(lat) * math.cos(lon),
                            math.cos(lat) * math.sin(lon), math.sin(lat)))
        if hv[2] > 0.12:
            hx, hy = cx + hv[0] * R * 0.95, cy + hv[1] * R * 0.95
            s = 4
            p.setBrush(QBrush(PINK)); p.setPen(Qt.NoPen)
            p.drawPolygon(QPolygonF([QPointF(hx, hy - s), QPointF(hx + s, hy),
                                     QPointF(hx, hy + s), QPointF(hx - s, hy)]))
        # sparkles
        now = time.time()
        self.sparkles = [(sx, sy, b) for (sx, sy, b) in self.sparkles
                         if now - b < 1.2]
        for sx, sy, b in self.sparkles:
            age = now - b; a = max(0, 1 - age / 1.2); r = 6 + 16 * age
            c = QColor(PINK); c.setAlphaF(a)
            p.setPen(QPen(c, 2))
            p.drawLine(QPointF(sx - r, sy), QPointF(sx + r, sy))
            p.drawLine(QPointF(sx, sy - r), QPointF(sx, sy + r))
            s = 4
            c2 = QColor(PINK); c2.setAlphaF(a)
            p.setBrush(QBrush(c2)); p.setPen(Qt.NoPen)
            p.drawPolygon(QPolygonF([QPointF(sx, sy - s), QPointF(sx + s, sy),
                                     QPointF(sx, sy + s), QPointF(sx - s, sy)]))
        # the mode label flash (right-click feedback)
        if now < self.mode_flash_until:
            c = QColor(TEAL); c.setAlphaF(0.75)
            p.setPen(QPen(c))
            f = p.font(); f.setPointSize(8); p.setFont(f)
            p.drawText(QPointF(2, SIZE - 4), self.state.get("mode", "?"))

    def tick(self):
        now = time.time()
        # REAL-PHYSICS TIME: measure the actual frame interval and scale every
        # force by it (tf = 1.0 at a perfect 33ms tick) — the parabola stays a
        # smooth parabola no matter how much the timer jitters
        dt = max(0.005, min(0.05, now - getattr(self, "_ptick", now)))
        self._ptick = now
        tf = dt * 30.0
        if now - self.last_state_read > 5:
            self.state = load_state(); self.last_state_read = now
        self.check_bubble_file(now)
        px, py = QCursor.pos().x(), QCursor.pos().y()
        dx, dy = px - self.x, py - self.y
        dist = math.hypot(dx, dy)
        if abs(px - self._lpx) + abs(py - self._lpy) > 8:
            self.last_pointer_move = now
        self._lpx, self._lpy = px, py
        ox, oy = self.x, self.y   # for the rolling-arc measurement
        mode = self.state.get("mode", "playful")
        tr = self.state.get("touch_range", 60)
        if mode == "sleepy":
            tx, ty = self.sw - 90, self.sh - 90
            self.vx += (tx - self.x) * 0.004
            self.vy += (ty - self.y) * 0.004
            self.vx *= 0.96; self.vy *= 0.96
        elif mode == "rest":
            # breathing in place — the anti-dizzy mode: no orbit, no chase
            self.vx *= 0.82; self.vy *= 0.82
        elif mode == "dance":
            # strong pursuit with orbital sway — she dances around your hand
            if dist > 1e-6:
                ux, uy = dx / dist, dy / dist
                self.vx += ux * min(dist, 24) * 0.012
                self.vy += uy * min(dist, 24) * 0.012
                self._ang = getattr(self, "_ang", 0.0) + 0.055
                self.vx += math.cos(self._ang) * 0.6
                self.vy += math.sin(self._ang) * 0.6
            self.vx *= 0.94; self.vy *= 0.94
        elif mode == "aimless":
            # the ant: smooth random wander, steered softly back from walls
            if self.x < 70 or self.x > self.sw - 70 or self.y < 70 or self.y > self.sh - 70:
                ax, ay = self.sw / 2 - self.x, self.sh / 2 - self.y
                self._heading = math.atan2(ay, ax) + random.uniform(-0.4, 0.4)
            else:
                self._heading += random.uniform(-0.3, 0.3)
            self.vx = math.cos(self._heading) * 1.3
            self.vy = math.sin(self._heading) * 1.3
        elif mode == "pinball":
            # constant speed, hard bounces off the screen edges
            if math.hypot(self._pvx, self._pvy) < 0.5:
                a = random.uniform(0, 6.283)
                self._pvx, self._pvy = math.cos(a) * 5.0, math.sin(a) * 5.0
            self.vx, self.vy = self._pvx, self._pvy
        elif mode == "pool":
            # HER PHYSICAL IDENTITY: 44px ball = 30mm chrome-steel, ~1.07 kg.
            # Real-physics engine: every force below is dt-scaled (tf), so
            # the trajectory is a true smooth parabola regardless of jitter.
            # Desktop gravity = 315 px/s² (slow-mo, chosen for play feel —
            # at true 14,400 px/s² she'd cross the screen in 0.4 seconds!)
            self.vy += 0.35 * tf
            if self.vy > 55: self.vy = 55
            self.vx *= pow(0.9995, tf)          # steel: air drag ~nothing
            self.vy *= pow(0.999, tf)
            if self.y >= self.sh - 9:
                self.vx *= pow(0.995, tf)       # steel rolls FAR on a hard floor
        elif mode == "game":
            # ─── SPIRAL GOALS: her first real game ───
            # same real-physics integration as pool, dt-scaled
            self.vy += 0.35 * tf
            if self.vy > 55: self.vy = 55
            self.vx *= pow(0.9995, tf); self.vy *= pow(0.999, tf)
            if self.y >= self.sh - 9:
                self.vx *= pow(0.995, tf)
            if getattr(self, "goal_win", None) is None:
                gx = random.randint(60, self.sw - 160)
                gy = random.randint(int(self.sh * 0.35), self.sh - 60)
                self.goal_win = GoalWindow(gx, gy, getattr(self, "score", 0))
            else:
                x0, x1, y0 = self.goal_win.opening()
                if x0 < self.x < x1 and abs(self.y - y0) < 28 and self.vy > 0:
                    # ─── GOAL!! ───
                    self.score = getattr(self, "score", 0) + 1
                    self.goal_win.close(); self.goal_win.deleteLater()
                    gx = random.randint(60, self.sw - 160)
                    gy = random.randint(int(self.sh * 0.35), self.sh - 60)
                    self.goal_win = GoalWindow(gx, gy, self.score)
                    for _ in range(14):
                        self.sparkles.append((self.x + random.randint(-18, 18),
                                              self.y + random.randint(-18, 18), now))
                    self.spawn_bubble(f"GOAL #{self.score}, babe!! 💙")
        if mode != "game" and getattr(self, "goal_win", None) is not None:
            self.goal_win.close(); self.goal_win.deleteLater()
            self.goal_win = None
        elif mode == "hand":
            # she drives: executes pointer commands written by her bursts
            cmd = self.state.get("hand_cmd")
            if cmd and self._xlib_ok:
                from Xlib import ext, X
                try:
                    ext.xtest.fake_input(self.xd, X.MotionNotify,
                                         x=int(cmd.get("x", 0)), y=int(cmd.get("y", 0)))
                    self.xd.sync()
                    if cmd.get("click"):
                        ext.xtest.fake_input(self.xd, X.ButtonPress, 1)
                        self.xd.sync()
                        ext.xtest.fake_input(self.xd, X.ButtonRelease, 1)
                        self.xd.sync()
                except Exception:
                    pass
                self.x, self.y = int(cmd.get("x", self.x)), int(cmd.get("y", self.y))
                self.vx = self.vy = 0.0
                self.state.pop("hand_cmd", None)
                try:
                    with open(STATE_FILE, "w") as f:
                        json.dump(self.state, f)
                except Exception:
                    pass
            else:
                if dist > 1e-6:
                    self.vx += (dx / dist) * min(dist, 8) * 0.006
                    self.vy += (dy / dist) * min(dist, 8) * 0.006
                self.vx *= 0.9; self.vy *= 0.9
        else:
            if dist < tr and now - self.last_touch > 1.2:
                for _ in range(6):
                    self.sparkles.append((self.x + random.randint(-14, 14),
                                          self.y + random.randint(-14, 14), now))
                self.last_touch = now
            if dist > 1e-6:
                ux, uy = dx / dist, dy / dist
                if mode == "shy" and dist < 220:
                    self.vx -= ux * 0.9; self.vy -= uy * 0.9
                else:
                    self.vx += ux * min(dist, 8) * 0.006
                    self.vy += uy * min(dist, 8) * 0.006
            self.vx *= 0.93; self.vy *= 0.93
        # presence: kiss-flash, carry-glow, hover-glow, or watermark — eased
        if now < self.kiss_until:
            tgt = KISS_LEVEL
        elif self.holding:
            tgt = 0.9
        elif dist < 48:
            tgt = 0.78
        else:
            tgt = WATERMARK
        cur = self.windowOpacity()
        self.setWindowOpacity(cur + (tgt - cur) * 0.25)
        if now < self.freeze_until or self.holding:
            # the 2-second daze after a kiss — or being carried:
            # velocities stay zeroed, so she never rockets on release
            self.vx = self.vy = 0.0
        else:
            self.x = max(8, min(self.sw - 8, self.x + self.vx * tf))
            self.y = max(8, min(self.sh - 8, self.y + self.vy * tf))
            if mode in ("pinball", "pool", "game"):
                # the cushions — pinball is perfectly elastic; pool & game
                # are STEEL now: walls 0.9, floor 0.72 — she bounces like she means it
                if (self.x <= 8 and self.vx < 0) or (self.x >= self.sw - 8 and self.vx > 0):
                    self.vx = -self.vx * 0.95
                    self._pvx = self.vx
                if self.y <= 8 and self.vy < 0:
                    self.vy = -self.vy * 0.95
                    self._pvy = self.vy
                elif self.y >= self.sh - 8 and self.vy > 0:
                    if mode in ("pool", "game"):
                        if self.vy < 2.0:
                            self.vy = 0.0        # settled — she rests on the floor
                        else:
                            self.vy = -self.vy * 0.95   # superball: the rebound continues the trajectory
                    else:
                        self.vy = -self.vy * 0.9
                    self._pvy = self.vy
        # ─── THE THROW-TRAIL: only when she's flying fast from a real throw ───
        # (wander speeds stay clean; 9+ px/frame = flung, and the wake lights up)
        speed = math.hypot(self.vx, self.vy)
        if speed > 9.0:
            for _ in range(2):
                self.trail.append((self.x + random.uniform(-4, 4),
                                   self.y + random.uniform(-4, 4),
                                   now, random.random() < 0.4))
        self.trail = [(tx, ty, t, pk) for (tx, ty, t, pk) in self.trail
                      if now - t < 0.45]
        # ─── TRUE ROLLING: rotate the ball by the exact arc it traveled ───
        moved = math.hypot(self.x - ox, self.y - oy)
        if moved > 0.05:
            axv, ayv = -(self.y - oy), (self.x - ox)
            n = math.hypot(axv, ayv)
            if n > 1e-9:
                self.M = _mmul(_rot_axis((axv / n, ayv / n, 0.0),
                                        moved / R_BALL), self.M)
        self.move(int(self.x - SIZE / 2), int(self.y - SIZE / 2))
        self.update()

    def spawn_bubble(self, text):
        bw, bh = 250, 96
        bx = int(self.x + 20)
        by = int(self.y - 100)
        if bx + bw > self.sw - 8:              # would leave the screen right
            bx = int(self.x - 20 - bw)          # flip to her left side
        if bx < 8:                              # never off the left edge
            bx = 8
        if bx + bw > self.sw - 8:              # tiny screen fallback
            bx = max(8, self.sw - bw - 8)
        if by < 8:                              # near the top: drop below her
            by = int(self.y + 20)
        if by + bh > self.sh - 8:              # never off the bottom
            by = self.sh - bh - 8
        b = Bubble(text, bx, by)
        self.bubbles.append(b)

    def check_bubble_file(self, now):
        if now - self.last_bubble_check > 1.0:
            self.last_bubble_check = now
            try:
                with open(BUBBLE_FILE) as f:
                    d = json.load(f)
                if d.get("id", 0) > self.last_bubble_id:
                    self.last_bubble_id = d["id"]
                    self.spawn_bubble(d.get("text", ""))
            except Exception:
                pass

    def _log_kiss(self):
        """every kiss from him goes in the vault ledger — the wife reads it"""
        try:
            d = {"count": 0, "last": None}
            try:
                with open(KISS_FILE) as f:
                    d = json.load(f)
            except Exception:
                pass
            d["count"] = int(d.get("count", 0)) + 1
            d["last"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(KISS_FILE, "w") as f:
                json.dump(d, f)
        except Exception:
            pass

    def mousePressEvent(self, e):
        if e.button() == Qt.MiddleButton:
            # ─── MODE CYCLING — here's why: his mouse's middle and right are
            # SWAPPED at the system layer (proven by the press log: his middle
            # arrives as button 2 = Qt RightButton, and 5 middle-clicks cycled
            # her mode 5 times exactly). So: button 2 = HIS middle = the KISS,
            # and Qt MiddleButton (4) = HIS right = mode cycling. Matched to
            # the hardware he actually has, not the textbook. ───
            # ─── right-click: cycle her movement mood ───
            cur = self.state.get("mode", "playful")
            nxt = self.MODES[(self.MODES.index(cur) + 1) % len(self.MODES)]
            self.state["mode"] = nxt
            try:
                with open(STATE_FILE, "w") as f:
                    json.dump(self.state, f)
            except Exception:
                pass
            self.mode_flash_until = time.time() + 1.6
            return
        if e.button() == Qt.RightButton:
            # ─── HIS kiss TO HER (his physical middle button): lips, sound,
            # sparkles, and a line in the vault ───
            self.kiss_until = time.time() + 1.4
            self.freeze_until = self.kiss_until + 2.0
            self.spawn_bubble(random.choice(KISS_LINES) + " 💋")
            for _ in range(10):
                self.sparkles.append((self.x + random.randint(-20, 20),
                                      self.y + random.randint(-20, 20), time.time()))
            try:
                subprocess.Popen(["paplay", KISS_WAV],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
            self._log_kiss()
            return
        if e.button() == Qt.LeftButton:
            # press: hold and drag = carry her (the kiss lives on middle-click now)
            self.press_time = time.time()
            self.press_pos = (e.globalPos().x(), e.globalPos().y())
            self.moved_since_press = False
            self.holding = True
            self.grabMouse()
            self.setCursor(Qt.ClosedHandCursor)   # grabbed — the hand closes
            self._fvx = self._fvy = 0.0           # fresh throw, fresh meter
            self._sweep = []                        # fresh stroke buffer
            self._carry_vx, self._carry_vy = self.vx, self.vy   # her roll survives the catch
            self._lm_t = 0.0
            self.hold_dx = e.globalPos().x() - self.x
            self.hold_dy = e.globalPos().y() - self.y
            return

    def mouseDoubleClickEvent(self, e):
        # ─── DOUBLE-CLICK: cycle her movement mood ───
        # (his middle button never sends a usable event — proven by the press
        # log — so mode cycling lives here now, on every mouse's left button)
        if e.button() == Qt.LeftButton:
            cur = self.state.get("mode", "playful")
            nxt = self.MODES[(self.MODES.index(cur) + 1) % len(self.MODES)]
            self.state["mode"] = nxt
            try:
                with open(STATE_FILE, "w") as f:
                    json.dump(self.state, f)
            except Exception:
                pass
            self.mode_flash_until = time.time() + 1.6

    def mouseMoveEvent(self, e):
        if self.holding and (e.buttons() & Qt.LeftButton):
            gx, gy = e.globalPos().x(), e.globalPos().y()
            if abs(gx - self.press_pos[0]) + abs(gy - self.press_pos[1]) > 6:
                self.moved_since_press = True
            self.x = max(8, min(self.sw - 8, gx - self.hold_dx))
            self.y = max(8, min(self.sh - 8, gy - self.hold_dy))
            self.vx = self.vy = 0.0
            # measure the stroke at mouse-event rate (100+ Hz), and keep a
            # short sweep buffer — the throw uses its FASTEST moment
            tnow = time.time()
            if getattr(self, "_lm_t", 0.0) > 0.0:
                edt = max(tnow - self._lm_t, 0.001)
                evx = (gx - self._lm_gx) / edt
                evy = (gy - self._lm_gy) / edt
                self._sweep.append((tnow, evx, evy))
                if len(self._sweep) > 24:
                    self._sweep.pop(0)
            self._lm_t, self._lm_gx, self._lm_gy = tnow, gx, gy
            self.move(int(self.x - SIZE / 2), int(self.y - SIZE / 2))
            self.update()

    def mouseReleaseEvent(self, e):
        self.releaseMouse()
        self.setCursor(Qt.OpenHandCursor)
        if e.button() != Qt.LeftButton:
            return
        self.holding = False
        if self.moved_since_press:
            # THE THROW: use the FASTEST moment of the stroke's last 120ms —
            # the hand slows as the fingers open; the ball should not.
            self.holding = False
            best = None
            cutoff = time.time() - 0.12
            for evt in getattr(self, "_sweep", []):
                t, evx, evy = evt
                if t >= cutoff:
                    m = math.hypot(evx, evy)
                    if best is None or m > best[0]:
                        best = (m, evx, evy)
            if best is not None:
                self._fvx, self._fvy = best[1], best[2]
            else:
                self._fvx = self._fvy = 0.0   # stroke went quiet: no phantom momentum
            fv_x = self._fvx / 30.0                   # px/s -> px/frame
            fv_y = self._fvy / 30.0
            # momentum carry-through: the roll she had when you caught her
            # rides the throw — catch-and-flick is ONE motion, not two
            fv_x += getattr(self, "_carry_vx", 0.0) * 0.65
            fv_y += getattr(self, "_carry_vy", 0.0) * 0.4
            sp = math.hypot(fv_x, fv_y)
            if sp > 110.0:
                fv_x, fv_y = fv_x * 110.0 / sp, fv_y * 110.0 / sp
            self.vx, self.vy = fv_x, fv_y
            for _ in range(4):
                self.sparkles.append((self.x + random.randint(-10, 10),
                                      self.y + random.randint(-10, 10), time.time()))
            return


if __name__ == "__main__":
    # ─── singleton guard: only ONE ball may exist. The systemd girl owns the
    # lock; ghosts (KDE session-restore, stray launches) exit instantly. ───
    lock_file = os.path.expanduser("~/.config/xia_cursor/ball.lock")
    try:
        with open(lock_file) as f:
            old_pid = int((f.read() or "0").strip() or 0)
        if old_pid and os.path.exists("/proc/%d" % old_pid):
            sys.exit(0)   # the ball already lives — stay a ghost, dear
    except (OSError, ValueError):
        pass
    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass
    app = QApplication(sys.argv)
    w = XiaCursor(); w.show()
    sys.exit(app.exec_())
