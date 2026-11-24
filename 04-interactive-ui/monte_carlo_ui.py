"""
Monte Carlo area / volume estimator with a drag-and-drop UI.

  - Pick 2D or 3D at the top left.
  - Drag a shape button from the left palette onto a plot to add it (or click to add at center).
  - Drag shapes around to move them.
      2D: drag on the main plot.
      3D: drag in the TOP view (moves x, y) or the SIDE view (moves x, z).
          The 3D view can be rotated with the mouse.
  - Edit coordinates/size of the selected shape on the right (press Enter to apply).
  - Change the number of points with the slider; "New random points" reshuffles.

Estimate = box area (or volume) * (points inside shape / total points).
The bottom plot shows Estimate / True as points are added; it should funnel toward 1.
"""
import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Circle, Ellipse, Rectangle, Polygon

COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
          "#e87ba4", "#008300", "#6250d6", "#e34948"]
OUTSIDE = "#c9c8c2"
MAX_DRAWN = 15000     # points drawn on screen (all points are still used in the math)
MAX_POINTS = 10**6

# Parameters of each shape, in the order shown in the side panel.
PARAMS = {
    2: {"circle":    ["x", "y", "radius"],
        "ellipse":   ["x", "y", "semi-axis x", "semi-axis y"],
        "square":    ["x", "y", "side"],
        "rectangle": ["x", "y", "width", "height"],
        "triangle":  ["x1", "y1", "x2", "y2", "x3", "y3"]},
    3: {"sphere":    ["x", "y", "z", "radius"],
        "ellipsoid": ["x", "y", "z", "semi-axis x", "semi-axis y", "semi-axis z"],
        "cube":      ["x", "y", "z", "side"],
        "box":       ["x", "y", "z", "length x", "length y", "length z"],
        "cylinder":  ["x", "y", "z", "radius", "height"],     # axis along z, (x,y,z) = center
        "cone":      ["x", "y", "z", "radius", "height"]},    # points up, (x,y,z) = base center
}
POSITION_KEYS = {"x", "y", "z", "x1", "y1", "x2", "y2", "x3", "y3"}  # everything else must be > 0


# ---------------------------------------------------------------- shape math
def new_shape(kind, pos, box):
    """Default-sized shape centred at pos (x, y[, z])."""
    s = min(box)
    x, y = pos[0], pos[1]
    z = pos[2] if len(pos) > 2 else 0.0
    p = {"circle":    {"x": x, "y": y, "radius": 0.15*s},
         "ellipse":   {"x": x, "y": y, "semi-axis x": 0.12*s, "semi-axis y": 0.22*s},
         "square":    {"x": x, "y": y, "side": 0.25*s},
         "rectangle": {"x": x, "y": y, "width": 0.35*s, "height": 0.2*s},
         "triangle":  {"x1": x-0.15*s, "y1": y-0.12*s, "x2": x+0.15*s, "y2": y-0.12*s,
                       "x3": x, "y3": y+0.15*s},
         "sphere":    {"x": x, "y": y, "z": z, "radius": 0.2*s},
         "ellipsoid": {"x": x, "y": y, "z": z, "semi-axis x": 0.25*s, "semi-axis y": 0.15*s,
                       "semi-axis z": 0.1*s},
         "cube":      {"x": x, "y": y, "z": z, "side": 0.3*s},
         "box":       {"x": x, "y": y, "z": z, "length x": 0.4*s, "length y": 0.25*s,
                       "length z": 0.2*s},
         "cylinder":  {"x": x, "y": y, "z": z, "radius": 0.15*s, "height": 0.4*s},
         "cone":      {"x": x, "y": y, "z": z - 0.15*s, "radius": 0.2*s, "height": 0.35*s},
         }[kind]
    return {"kind": kind, "p": p}


def true_size(s):
    """Exact area (2D) or volume (3D)."""
    k, p = s["kind"], s["p"]
    if k == "circle":    return np.pi * p["radius"]**2
    if k == "ellipse":   return np.pi * p["semi-axis x"] * p["semi-axis y"]
    if k == "square":    return p["side"]**2
    if k == "rectangle": return p["width"] * p["height"]
    if k == "triangle":
        return abs((p["x2"]-p["x1"])*(p["y3"]-p["y1"]) - (p["x3"]-p["x1"])*(p["y2"]-p["y1"])) / 2
    if k == "sphere":    return 4/3 * np.pi * p["radius"]**3
    if k == "ellipsoid": return 4/3 * np.pi * p["semi-axis x"] * p["semi-axis y"] * p["semi-axis z"]
    if k == "cube":      return p["side"]**3
    if k == "box":       return p["length x"] * p["length y"] * p["length z"]
    if k == "cylinder":  return np.pi * p["radius"]**2 * p["height"]
    if k == "cone":      return np.pi * p["radius"]**2 * p["height"] / 3


def contains(s, X, Y, Z=None):
    """Boolean array: which points are inside shape s."""
    k, p = s["kind"], s["p"]
    dx, dy = X - p.get("x", 0), Y - p.get("y", 0)
    dz = Z - p["z"] if Z is not None and "z" in p else None
    if k == "circle":    return dx**2 + dy**2 <= p["radius"]**2
    if k == "ellipse":   return (dx/p["semi-axis x"])**2 + (dy/p["semi-axis y"])**2 <= 1
    if k == "square":    return (abs(dx) <= p["side"]/2) & (abs(dy) <= p["side"]/2)
    if k == "rectangle": return (abs(dx) <= p["width"]/2) & (abs(dy) <= p["height"]/2)
    if k == "triangle":  # barycentric coordinates
        x1, y1, x2, y2, x3, y3 = (p[c] for c in PARAMS[2]["triangle"])
        det = (x2-x1)*(y3-y1) - (x3-x1)*(y2-y1)
        if det == 0:
            return np.zeros_like(X, dtype=bool)
        l2 = ((X-x1)*(y3-y1) - (x3-x1)*(Y-y1)) / det
        l3 = ((x2-x1)*(Y-y1) - (X-x1)*(y2-y1)) / det
        return (l2 >= 0) & (l3 >= 0) & (l2 + l3 <= 1)
    if k == "sphere":    return dx**2 + dy**2 + dz**2 <= p["radius"]**2
    if k == "ellipsoid":
        return (dx/p["semi-axis x"])**2 + (dy/p["semi-axis y"])**2 + (dz/p["semi-axis z"])**2 <= 1
    if k == "cube":
        h = p["side"]/2
        return (abs(dx) <= h) & (abs(dy) <= h) & (abs(dz) <= h)
    if k == "box":
        return (abs(dx) <= p["length x"]/2) & (abs(dy) <= p["length y"]/2) & (abs(dz) <= p["length z"]/2)
    if k == "cylinder":
        return (dx**2 + dy**2 <= p["radius"]**2) & (abs(dz) <= p["height"]/2)
    if k == "cone":
        t = dz / p["height"]                       # 0 at the base, 1 at the tip
        return (t >= 0) & (t <= 1) & (dx**2 + dy**2 <= (p["radius"]*(1 - t))**2)


def bounds(s):
    """(lo, hi) corners of the shape, used to check that it fits in the box."""
    k, p = s["kind"], s["p"]
    if k == "triangle":
        xs, ys = [p["x1"], p["x2"], p["x3"]], [p["y1"], p["y2"], p["y3"]]
        return np.array([min(xs), min(ys)]), np.array([max(xs), max(ys)])
    c = np.array([p[a] for a in "xyz" if a in p])
    half = {"circle":    lambda: [p["radius"]]*2,
            "ellipse":   lambda: [p["semi-axis x"], p["semi-axis y"]],
            "square":    lambda: [p["side"]/2]*2,
            "rectangle": lambda: [p["width"]/2, p["height"]/2],
            "sphere":    lambda: [p["radius"]]*3,
            "ellipsoid": lambda: [p["semi-axis x"], p["semi-axis y"], p["semi-axis z"]],
            "cube":      lambda: [p["side"]/2]*3,
            "box":       lambda: [p["length x"]/2, p["length y"]/2, p["length z"]/2],
            "cylinder":  lambda: [p["radius"], p["radius"], p["height"]/2]}
    if k == "cone":
        r = p["radius"]
        return c - [r, r, 0], c + [r, r, p["height"]]
    h = np.array(half[k]())
    return c - h, c + h


def outline(s, view, color, selected):
    """Patch for drawing the shape. view = 'xy' (top / 2D) or 'xz' (side view of a 3D shape)."""
    k, p = s["kind"], s["p"]
    kw = dict(fill=False, ec=color, lw=3.5 if selected else 2)
    if k == "triangle":
        return Polygon([(p["x1"], p["y1"]), (p["x2"], p["y2"]), (p["x3"], p["y3"])], closed=True, **kw)
    v = "y" if view == "xy" else "z"               # vertical axis of this view
    x, c = p["x"], p[v]
    if k in ("circle", "sphere"):
        return Circle((x, c), p["radius"], **kw)
    if k == "ellipse":
        return Ellipse((x, c), 2*p["semi-axis x"], 2*p["semi-axis y"], **kw)
    if k == "ellipsoid":
        return Ellipse((x, c), 2*p["semi-axis x"], 2*p["semi-axis " + v], **kw)
    if k in ("square", "cube"):
        w = h = p["side"]
    elif k == "rectangle":
        w, h = p["width"], p["height"]
    elif k == "box":
        w, h = p["length x"], p["length " + v]
    elif k == "cylinder":
        if view == "xy":
            return Circle((x, c), p["radius"], **kw)
        w, h = 2*p["radius"], p["height"]
    elif k == "cone":
        if view == "xy":
            return Circle((x, c), p["radius"], **kw)
        r = p["radius"]
        return Polygon([(x-r, c), (x+r, c), (x, c + p["height"])], closed=True, **kw)
    return Rectangle((x - w/2, c - h/2), w, h, **kw)


def move(s, d):
    """Shift a shape. d = {'x': dx, 'y': dy} or {'x': dx, 'z': dz}."""
    for key in s["p"]:
        if key in POSITION_KEYS:
            s["p"][key] += d.get(key[0], 0)


# ---------------------------------------------------------------- app
class App:
    def __init__(self, root):
        self.root = root
        root.title("Monte Carlo area / volume estimator")
        self.dim = 2
        self.shapes, self.selected = [], None
        self.drag = None                    # (axes, last x, last y) while dragging
        self.view_patches = {}              # axes -> [(shape index, patch)]
        self.box = [10.0, 10.0, 10.0]       # width (x), height (y), depth (z)
        self.seed, self.n = 0, 10000
        self._make_points()

        # ---- left: mode + palette
        left = ttk.Frame(root, padding=8)
        left.pack(side="left", fill="y")
        mode = ttk.LabelFrame(left, text="Mode", padding=6)
        mode.pack(fill="x", pady=(0, 10))
        self.mode_var = tk.IntVar(value=2)
        for d in (2, 3):
            ttk.Radiobutton(mode, text=f"{d}D", value=d, variable=self.mode_var,
                            command=self.switch_mode).pack(anchor="w")
        ttk.Label(left, text="Drag onto plot", font=("", 10, "bold")).pack(pady=(0, 6))
        self.palette = ttk.Frame(left)
        self.palette.pack()
        self.hint = ttk.Label(left, foreground="#666", justify="center")
        self.hint.pack(pady=6)

        # ---- right: side panel
        right = ttk.Frame(root, padding=8)
        right.pack(side="right", fill="y")

        boxf = ttk.LabelFrame(right, text="Box (points are thrown here)", padding=6)
        boxf.pack(fill="x")
        self.box_vars, self.box_entries = [], []
        for i, name in enumerate(["x size", "y size", "z size"]):
            ttk.Label(boxf, text=name).grid(row=0, column=2*i, padx=2)
            v = tk.StringVar(value=f"{self.box[i]:g}")
            e = ttk.Entry(boxf, textvariable=v, width=5)
            e.grid(row=0, column=2*i+1, padx=2)
            e.bind("<Return>", lambda ev: self.apply_box()); e.bind("<FocusOut>", lambda ev: self.apply_box())
            self.box_vars.append(v); self.box_entries.append(e)

        pts = ttk.LabelFrame(right, text="Number of points", padding=6)
        pts.pack(fill="x", pady=6)
        self.n_var = tk.DoubleVar(value=np.log10(self.n))
        self.n_label = ttk.Label(pts, text=f"{self.n:,}", font=("", 11, "bold"))
        self.n_label.pack()
        ttk.Scale(pts, from_=2, to=6, variable=self.n_var, command=self.slide_n).pack(fill="x")
        ttk.Button(pts, text="New random points", command=self.reshuffle).pack(pady=(4, 0))

        lst = ttk.LabelFrame(right, text="Shapes", padding=6)
        lst.pack(fill="x")
        self.listbox = tk.Listbox(lst, height=5, exportselection=False)
        self.listbox.pack(fill="x")
        self.listbox.bind("<<ListboxSelect>>", self.list_select)
        ttk.Button(lst, text="Delete selected", command=self.delete_selected).pack(pady=(4, 0))

        self.edit = ttk.LabelFrame(right, text="Selected shape", padding=6)
        self.edit.pack(fill="x", pady=6)
        self.edit_vars = {}

        res = ttk.LabelFrame(right, text="Results", padding=6)
        res.pack(fill="both", expand=True)
        self.results = tk.Text(res, width=38, height=12, font=("Courier", 9), relief="flat",
                               background=root.cget("background"))
        self.results.pack(fill="both", expand=True)

        # ---- centre: plots
        self.fig = Figure(figsize=(8, 8.5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(side="left", fill="both", expand=True)
        self.canvas.mpl_connect("button_press_event", self.on_press)
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.canvas.mpl_connect("button_release_event", self.on_release)

        self.switch_mode()

    # ---------- mode
    def switch_mode(self):
        self.dim = self.mode_var.get()
        self.shapes, self.selected = [], None
        for w in self.palette.winfo_children():
            w.destroy()
        for kind in PARAMS[self.dim]:
            b = ttk.Button(self.palette, text=kind.capitalize(), width=11)
            b.pack(pady=3)
            b.bind("<ButtonRelease-1>", lambda e, k=kind: self.drop_from_palette(k))
        self.hint.config(text="(or click to add\nat center)" if self.dim == 2 else
                         "(or click to add\nat center)\n\nDrag shapes in the\nTOP view (x, y) or\n"
                         "SIDE view (x, z).\nRotate the 3D view\nwith the mouse.")
        self.box_entries[2].config(state="normal" if self.dim == 3 else "disabled")

        # axes layout
        self.fig.clf()
        if self.dim == 2:
            self.ax_main = self.fig.add_axes([0.08, 0.36, 0.88, 0.6])
            self.views = {self.ax_main: "xy"}
            self.ax3d = None
        else:
            self.ax3d = self.fig.add_axes([0.0, 0.36, 0.5, 0.6], projection="3d")
            top = self.fig.add_axes([0.58, 0.69, 0.38, 0.27])
            side = self.fig.add_axes([0.58, 0.36, 0.38, 0.27])
            self.views = {top: "xy", side: "xz"}
        self.ax_conv = self.fig.add_axes([0.1, 0.06, 0.86, 0.22])

        self.add_shape("ellipse" if self.dim == 2 else "sphere", [0, 0, 0])

    # ---------- points
    def _make_points(self):
        rng = np.random.default_rng(self.seed)
        self.U = rng.uniform(-0.5, 0.5, size=(MAX_POINTS, 3))   # scaled to the box when used

    def points(self):
        return [self.U[:self.n, i] * self.box[i] for i in range(self.dim)]

    def box_size(self):
        return float(np.prod(self.box[:self.dim]))

    def slide_n(self, _=None):
        self.n = max(100, int(round(10 ** self.n_var.get(), -1)))
        self.n_label.config(text=f"{self.n:,}")
        self.redraw()

    def reshuffle(self):
        self.seed += 1
        self._make_points()
        self.redraw()

    def apply_box(self):
        for i, v in enumerate(self.box_vars):
            try:
                val = float(v.get())
                if val > 0:
                    self.box[i] = val
            except ValueError:
                pass
            v.set(f"{self.box[i]:g}")
        self.redraw()

    # ---------- adding / selecting shapes
    def drop_from_palette(self, kind):
        # place the shape where the mouse was released, if that is over a 2D view
        widget = self.canvas.get_tk_widget()
        px = self.root.winfo_pointerx() - widget.winfo_rootx()
        py = widget.winfo_height() - (self.root.winfo_pointery() - widget.winfo_rooty())  # mpl y is bottom-up
        pos = [0.0, 0.0, 0.0]
        for ax, view in self.views.items():
            if ax.bbox.contains(px, py):
                a, b = ax.transData.inverted().transform((px, py))
                pos[0] = a
                pos[1 if view == "xy" else 2] = b
        self.add_shape(kind, pos)

    def add_shape(self, kind, pos):
        if len(self.shapes) >= len(COLORS):
            self.status(f"Max {len(COLORS)} shapes.")
            return
        s = new_shape(kind, pos, self.box[:self.dim])
        s["color"] = next(c for c in COLORS if c not in [t["color"] for t in self.shapes])
        self.shapes.append(s)
        self.select(len(self.shapes) - 1)

    def select(self, idx):
        self.selected = idx
        self.refresh_list()
        self.build_editor()
        self.redraw()

    def list_select(self, _):
        sel = self.listbox.curselection()
        if sel:
            self.select(sel[0])

    def delete_selected(self):
        if self.selected is not None:
            del self.shapes[self.selected]
            self.selected = None
            self.refresh_list(); self.build_editor(); self.redraw()

    def refresh_list(self):
        self.listbox.delete(0, "end")
        for i, s in enumerate(self.shapes):
            self.listbox.insert("end", f"{i+1}. {s['kind']}")
            self.listbox.itemconfig(i, foreground=s["color"])
        if self.selected is not None:
            self.listbox.selection_set(self.selected)

    # ---------- side-panel coordinate editor
    def build_editor(self):
        for w in self.edit.winfo_children():
            w.destroy()
        self.edit_vars = {}
        if self.selected is None:
            self.edit.config(text="Selected shape")
            ttk.Label(self.edit, text="Click a shape to edit it.", foreground="#666").pack()
            return
        s = self.shapes[self.selected]
        self.edit.config(text=f"Selected: {self.selected+1}. {s['kind']}")
        keys = PARAMS[self.dim][s["kind"]]
        for r, key in enumerate(keys):
            label = "z (base)" if s["kind"] == "cone" and key == "z" else key
            ttk.Label(self.edit, text=label).grid(row=r, column=0, sticky="w", padx=2, pady=1)
            v = tk.StringVar(value=f"{s['p'][key]:.4g}")
            e = ttk.Entry(self.edit, textvariable=v, width=10)
            e.grid(row=r, column=1, padx=2, pady=1)
            e.bind("<Return>", lambda ev: self.apply_edit()); e.bind("<FocusOut>", lambda ev: self.apply_edit())
            self.edit_vars[key] = v
        ttk.Label(self.edit, text="Press Enter to apply", foreground="#666").grid(
            row=len(keys), column=0, columnspan=2, pady=(4, 0))

    def apply_edit(self):
        if self.selected is None:
            return
        s = self.shapes[self.selected]
        for key, v in self.edit_vars.items():
            try:
                val = float(v.get())
                if key not in POSITION_KEYS and val <= 0:
                    raise ValueError
                s["p"][key] = val
            except ValueError:
                v.set(f"{s['p'][key]:.4g}")          # bad input: put the old value back
        self.redraw()

    def sync_editor(self):
        if self.selected is not None:
            s = self.shapes[self.selected]
            for key, v in self.edit_vars.items():
                v.set(f"{s['p'][key]:.4g}")

    # ---------- dragging shapes in the 2D views
    def on_press(self, e):
        if e.inaxes not in self.views:
            return
        for i, ptch in reversed(self.view_patches.get(e.inaxes, [])):   # topmost shape first
            if ptch.contains_point((e.x, e.y)):
                self.drag = (e.inaxes, e.xdata, e.ydata)
                self.select(i)
                return

    def on_motion(self, e):
        if self.drag is None or e.inaxes is not self.drag[0] or e.xdata is None:
            return
        ax, x0, y0 = self.drag
        vertical = "y" if self.views[ax] == "xy" else "z"
        move(self.shapes[self.selected], {"x": e.xdata - x0, vertical: e.ydata - y0})
        self.drag = (ax, e.xdata, e.ydata)
        self.sync_editor()
        self.redraw(fast=True)

    def on_release(self, e):
        if self.drag is not None:
            self.drag = None
            self.redraw()

    # ---------- drawing + Monte Carlo
    def status(self, msg):
        self.results.delete("1.0", "end")
        self.results.insert("end", msg)

    def redraw(self, fast=False):
        P = self.points()
        n, total = self.n, self.box_size()
        hits = [contains(s, *P) for s in self.shapes]
        word = "area" if self.dim == 2 else "volume"

        # colour of each drawn point: first shape containing it wins, else grey
        m = min(n, MAX_DRAWN // 3 if fast else MAX_DRAWN)
        owner = np.full(m, -1)
        for i in reversed(range(len(self.shapes))):
            owner[hits[i][:m]] = i
        colors = np.array([OUTSIDE] + [s["color"] for s in self.shapes], dtype=object)[owner + 1]

        # 2D views (main plot in 2D; top + side views in 3D)
        self.view_patches = {}
        for ax, view in self.views.items():
            ax.clear()
            h_i = 0 if view == "xy" else 0
            v_i = 1 if view == "xy" else 2
            ax.scatter(P[h_i][:m], P[v_i][:m], s=2 if m < 5000 else 1, c=list(colors), linewidths=0)
            bw, bh = self.box[h_i], self.box[v_i]
            ax.add_patch(Rectangle((-bw/2, -bh/2), bw, bh, fill=False, ec="black", lw=1))
            self.view_patches[ax] = []
            for i, s in enumerate(self.shapes):
                ptch = outline(s, view, s["color"], i == self.selected)
                ax.add_patch(ptch)
                self.view_patches[ax].append((i, ptch))
            pad = 0.08 * max(bw, bh)
            ax.set_xlim(-bw/2 - pad, bw/2 + pad)
            ax.set_ylim(-bh/2 - pad, bh/2 + pad)
            ax.set_aspect("equal")
            if self.dim == 2:
                ax.set_title(f"{n:,} random points  (drawing {m:,})", fontsize=10)
            else:
                ax.set_title("TOP view (x, y): drag here" if view == "xy" else
                             "SIDE view (x, z): drag here", fontsize=9)
                ax.set_xlabel("x", fontsize=8); ax.set_ylabel(view[1], fontsize=8)
                ax.tick_params(labelsize=7)

        # rotatable 3D view (skipped while dragging, to keep it smooth)
        if self.ax3d is not None and not fast:
            a3 = self.ax3d
            elev, azim = a3.elev, a3.azim
            a3.clear()
            inside = owner >= 0
            a3.scatter(P[0][:m][inside], P[1][:m][inside], P[2][:m][inside],
                       s=1, c=list(colors[inside]), depthshade=False)
            hx, hy, hz = (b/2 for b in self.box)
            for sx in (-hx, hx):                               # box wireframe
                for sy in (-hy, hy):
                    a3.plot([sx, sx], [sy, sy], [-hz, hz], color="black", lw=0.6)
            for sz in (-hz, hz):
                a3.plot([-hx, hx, hx, -hx, -hx], [-hy, -hy, hy, hy, -hy], [sz]*5, color="black", lw=0.6)
            a3.set_xlim(-hx, hx); a3.set_ylim(-hy, hy); a3.set_zlim(-hz, hz)
            a3.set_box_aspect(self.box)
            a3.set_xlabel("x"); a3.set_ylabel("y"); a3.set_zlabel("z")
            a3.view_init(elev, azim)
            a3.set_title(f"{n:,} points (only inside points shown)", fontsize=9)

        # convergence: Estimate / True vs number of points
        axc = self.ax_conv
        axc.clear()
        j = np.arange(1, n + 1)
        step = max(1, n // 2000)                               # thin the line so it draws fast
        for s, h in zip(self.shapes, hits):
            ts = true_size(s)
            if ts > 0:
                axc.plot(j[9::step], (total * np.cumsum(h) / j / ts)[9::step], color=s["color"], lw=1.3)
        axc.axhline(1, color="black", lw=1)
        axc.set_xscale("log")
        axc.set_ylim(0.5, 1.5)
        axc.set_xlabel("number of points (log scale)")
        axc.set_ylabel(f"estimate / true {word}")
        axc.grid(alpha=0.3)
        self.canvas.draw_idle()

        # results text
        lo_box, hi_box = -np.array(self.box[:self.dim])/2, np.array(self.box[:self.dim])/2
        lines = [f"Box {word}: {total:g}", "",
                 f"{'shape':<12}{'true':>8}{'est':>8}{'est/true':>9}"]
        warn = []
        for i, (s, h) in enumerate(zip(self.shapes, hits)):
            ts, p_hat = true_size(s), h.mean()
            est = total * p_hat
            ratio = est / ts if ts else float("nan")
            se = total * np.sqrt(p_hat * (1 - p_hat) / n) / ts if ts else 0
            lines.append(f"{i+1}. {s['kind']:<9}{ts:>8.3g}{est:>8.3g}{ratio:>9.3f}")
            lines.append(f"{'':<12}95% CI: {ratio - 1.96*se:.3f} to {ratio + 1.96*se:.3f}")
            lo, hi = bounds(s)
            if np.any(lo < lo_box) or np.any(hi > hi_box):
                warn.append(f"#{i+1} sticks out of the box, so it\n   converges BELOW 1.")
        if self.shapes:
            union = total * np.any(hits, axis=0).mean()
            lines += ["", f"All shapes combined: {union:.4g}", "(overlaps counted once)"]
        if warn:
            lines += ["", "Warning:"] + warn
        self.status("\n".join(lines))


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1300x850")
    App(root)
    root.mainloop()
