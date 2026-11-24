"""
Monte Carlo area / volume estimator for several shapes inside a box.

1. Choose 2D (area) or 3D (volume).
2. Define the bounding box (where the random points are thrown).
3. Choose how many shapes, which kind, their size, and where they sit.
4. Choose how many points and how many independent runs.

For every shape it reports the estimate, the true value, Estimate/True,
and a 95% confidence interval, then plots:
  - the points and shapes,
  - Estimate/True vs number of points (should funnel toward 1),
  - (if more than one run) a histogram of the final Estimate/True values.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, Rectangle, Polygon

COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
          "#e87ba4", "#008300", "#6250d6", "#e34948"]
MAX_SHAPES = len(COLORS)
OUTSIDE = "#b5b4ad"


# ---------------------------------------------------------------- input helpers
def ask_float(prompt, positive=False):
    while True:
        try:
            v = float(input(prompt))
            if positive and v <= 0:
                print("  Must be greater than 0.")
                continue
            return v
        except ValueError:
            print("  Please enter a number.")


def ask_int(prompt, lo=1, hi=None, default=None):
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            return default
        try:
            v = int(raw)
            if v < lo or (hi is not None and v > hi):
                raise ValueError
            return v
        except ValueError:
            rng = f"{lo}-{hi}" if hi else f">= {lo}"
            print(f"  Please enter a whole number ({rng}).")


def ask_choice(prompt, options):
    """Accept either the option name or its number in the list."""
    for i, name in enumerate(options, 1):
        print(f"  {i}. {name}")
    while True:
        raw = input(prompt).strip().lower()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw in options:
            return raw
        print(f"  Choose one of: {', '.join(options)} (or its number).")


def ask_point(label, dim):
    axes = "xyz"[:dim]
    return np.array([ask_float(f"    {label} {a}: ") for a in axes])


# ---------------------------------------------------------------- shapes
# Each shape is a dict with:
#   name, contains(P) -> bool array, true (exact area/volume),
#   lo/hi (its bounding corners, used to check it fits in the box),
#   draw(ax, color) for 2D outlines.

def make_circle():
    c = ask_point("center", 2); r = ask_float("    radius: ", True)
    return dict(name="circle", true=np.pi * r**2, lo=c - r, hi=c + r,
                contains=lambda P: ((P - c)**2).sum(1) <= r**2,
                draw=lambda ax, col: ax.add_patch(Circle(c, r, fill=False, ec=col, lw=2)))


def make_ellipse():
    c = ask_point("center", 2)
    a = ask_float("    semi-axis along x: ", True)
    b = ask_float("    semi-axis along y: ", True)
    return dict(name="ellipse", true=np.pi * a * b, lo=c - [a, b], hi=c + [a, b],
                contains=lambda P: ((P[:, 0]-c[0])/a)**2 + ((P[:, 1]-c[1])/b)**2 <= 1,
                draw=lambda ax, col: ax.add_patch(Ellipse(c, 2*a, 2*b, fill=False, ec=col, lw=2)))


def make_rect(square):
    c = ask_point("center", 2)
    if square:
        w = h = ask_float("    side length: ", True)
    else:
        w = ask_float("    width (x): ", True); h = ask_float("    height (y): ", True)
    half = np.array([w, h]) / 2
    return dict(name="square" if square else "rectangle", true=w * h, lo=c - half, hi=c + half,
                contains=lambda P: np.all(np.abs(P - c) <= half, axis=1),
                draw=lambda ax, col: ax.add_patch(Rectangle(c - half, w, h, fill=False, ec=col, lw=2)))


def make_triangle():
    V = np.array([ask_point(f"vertex {i}", 2) for i in (1, 2, 3)])
    (x1, y1), (x2, y2), (x3, y3) = V
    det = (x2 - x1)*(y3 - y1) - (x3 - x1)*(y2 - y1)
    if det == 0:
        raise ValueError("Those three vertices are on a line (zero area).")

    def contains(P):
        # barycentric coordinates
        l2 = ((P[:, 0]-x1)*(y3-y1) - (x3-x1)*(P[:, 1]-y1)) / det
        l3 = ((x2-x1)*(P[:, 1]-y1) - (P[:, 0]-x1)*(y2-y1)) / det
        return (l2 >= 0) & (l3 >= 0) & (l2 + l3 <= 1)
    return dict(name="triangle", true=abs(det)/2, lo=V.min(0), hi=V.max(0), contains=contains,
                draw=lambda ax, col: ax.add_patch(Polygon(V, closed=True, fill=False, ec=col, lw=2)))


def make_sphere():
    c = ask_point("center", 3); r = ask_float("    radius: ", True)
    return dict(name="sphere", true=4/3*np.pi*r**3, lo=c - r, hi=c + r,
                contains=lambda P: ((P - c)**2).sum(1) <= r**2)


def make_ellipsoid():
    c = ask_point("center", 3)
    s = np.array([ask_float(f"    semi-axis along {a}: ", True) for a in "xyz"])
    return dict(name="ellipsoid", true=4/3*np.pi*s.prod(), lo=c - s, hi=c + s,
                contains=lambda P: (((P - c)/s)**2).sum(1) <= 1)


def make_box(cube):
    c = ask_point("center", 3)
    if cube:
        s = np.full(3, ask_float("    side length: ", True))
    else:
        s = np.array([ask_float(f"    length along {a}: ", True) for a in "xyz"])
    half = s / 2
    return dict(name="cube" if cube else "box", true=s.prod(), lo=c - half, hi=c + half,
                contains=lambda P: np.all(np.abs(P - c) <= half, axis=1))


def make_cylinder():
    c = ask_point("center", 3)
    r = ask_float("    radius: ", True); h = ask_float("    height (along z): ", True)
    return dict(name="cylinder", true=np.pi*r**2*h,
                lo=c - [r, r, h/2], hi=c + [r, r, h/2],
                contains=lambda P: (((P[:, :2]-c[:2])**2).sum(1) <= r**2) & (np.abs(P[:, 2]-c[2]) <= h/2))


def make_cone():
    c = ask_point("base center", 3)
    r = ask_float("    base radius: ", True); h = ask_float("    height (points up along z): ", True)

    def contains(P):
        t = (P[:, 2] - c[2]) / h                      # 0 at base, 1 at tip
        return (t >= 0) & (t <= 1) & (((P[:, :2]-c[:2])**2).sum(1) <= (r*(1 - t))**2)
    return dict(name="cone", true=np.pi*r**2*h/3, lo=c - [r, r, 0], hi=c + [r, r, h],
                contains=contains)


SHAPES_2D = {"circle": make_circle, "ellipse": make_ellipse,
             "square": lambda: make_rect(True), "rectangle": lambda: make_rect(False),
             "triangle": make_triangle}
SHAPES_3D = {"sphere": make_sphere, "ellipsoid": make_ellipsoid,
             "cube": lambda: make_box(True), "box": lambda: make_box(False),
             "cylinder": make_cylinder, "cone": make_cone}


# ---------------------------------------------------------------- simulation
def run_once(rng, box_lo, box_hi, shapes, n):
    """Throw n points; return the points and an (n_shapes x n) array of running Estimate/True."""
    dim = len(box_lo)
    P = rng.uniform(box_lo, box_hi, size=(n, dim))
    box_vol = np.prod(box_hi - box_lo)
    j = np.arange(1, n + 1)
    hits = np.array([s["contains"](P) for s in shapes])           # shape x point
    running = box_vol * np.cumsum(hits, axis=1) / j / np.array([s["true"] for s in shapes])[:, None]
    union = hits.any(0)
    return P, hits, running, box_vol * union.mean()


def main():
    print("Monte Carlo shape estimator")
    while True:
        mode = input("2D or 3D? ").strip().lower()
        if mode in ("2", "2d", "3", "3d"):
            break
        print("  Type 2D or 3D.")
    dim = 2 if mode.startswith("2") else 3
    word = "area" if dim == 2 else "volume"
    catalog = SHAPES_2D if dim == 2 else SHAPES_3D

    # --- bounding box
    print("\nBounding box (where random points are thrown):")
    bc = ask_point("center", dim)
    bs = np.array([ask_float(f"    size along {a}: ", True) for a in "xyz"[:dim]])
    box_lo, box_hi = bc - bs/2, bc + bs/2
    box_vol = bs.prod()

    # --- shapes
    k = ask_int(f"\nHow many shapes (1-{MAX_SHAPES})? ", 1, MAX_SHAPES)
    shapes = []
    for i in range(k):
        print(f"\nShape {i+1}:")
        kind = ask_choice("  type: ", list(catalog))
        while True:
            try:
                s = catalog[kind]()
                break
            except ValueError as e:
                print(f"  {e} Try again.")
        if np.any(s["lo"] < box_lo) or np.any(s["hi"] > box_hi):
            print(f"  WARNING: this {kind} sticks out of the box. Only the part inside is sampled,"
                  f"\n  so Estimate/True will converge BELOW 1 for it.")
        print(f"  true {word} = {s['true']:.6g}")
        s["color"] = COLORS[i]
        s["label"] = f"{i+1}. {kind}"
        shapes.append(s)

    n = ask_int("\nNumber of random points per run [default 10000]: ", 10, default=10000)
    runs = ask_int("Number of independent runs [default 1]: ", 1, default=1)
    seed_raw = input("Random seed (blank = random): ").strip()
    rng = np.random.default_rng(int(seed_raw) if seed_raw.lstrip("-").isdigit() else None)

    # --- run
    all_running, finals, union_est = [], [], []
    for r in range(runs):
        P, hits, running, u = run_once(rng, box_lo, box_hi, shapes, n)
        if r == 0:
            P0, hits0 = P, hits
        all_running.append(running)
        finals.append(running[:, -1])
        union_est.append(u)
    all_running = np.array(all_running)      # runs x shapes x n
    finals = np.array(finals)                # runs x shapes

    # --- report (based on run 1, plus spread across runs if runs > 1)
    print(f"\nBox {word}: {box_vol:.6g}   points per run: {n}   runs: {runs}")
    print(f"{'shape':<14}{'true':>12}{'estimate':>12}{'est/true':>10}{'95% CI (est/true)':>24}")
    for si, s in enumerate(shapes):
        p_hat = hits0[si].mean()
        est = box_vol * p_hat
        se = box_vol * np.sqrt(p_hat * (1 - p_hat) / n)
        lo, hi = (est - 1.96*se)/s["true"], (est + 1.96*se)/s["true"]
        print(f"{s['label']:<14}{s['true']:>12.5g}{est:>12.5g}{est/s['true']:>10.4f}"
              f"{f'[{lo:.4f}, {hi:.4f}]':>24}")
    print(f"Union of all shapes (overlaps counted once), run 1: {union_est[0]:.5g}")
    if runs > 1:
        print(f"\nAcross {runs} runs (final est/true):")
        for si, s in enumerate(shapes):
            f = finals[:, si]
            print(f"  {s['label']:<12} mean {f.mean():.4f}   sd {f.std(ddof=1):.4f}"
                  f"   runs above 1: {(f > 1).sum()}/{runs}")

    plot(dim, box_lo, box_hi, shapes, P0, hits0, all_running, finals, n, runs, word)
    plt.show()


# ---------------------------------------------------------------- plots
def plot(dim, box_lo, box_hi, shapes, P, hits, all_running, finals, n, runs, word):
    box_vol = np.prod(box_hi - box_lo)
    show = min(n, 20000)                       # don't draw millions of dots

    # 1. points and shapes
    fig1 = plt.figure(figsize=(7, 7))
    owner = np.full(n, -1)
    for si in range(len(shapes)):              # colour each point by the first shape containing it
        owner[(owner == -1) & hits[si]] = si
    if dim == 2:
        ax = fig1.add_subplot()
        out = owner[:show] == -1
        ax.scatter(*P[:show][out].T, s=1, color=OUTSIDE)
        for si, s in enumerate(shapes):
            m = owner[:show] == si
            ax.scatter(*P[:show][m].T, s=1, color=s["color"])
            s["draw"](ax, s["color"])
        ax.add_patch(Rectangle(box_lo, *(box_hi - box_lo), fill=False, ec="black"))
        ax.set_aspect("equal")
    else:
        ax = fig1.add_subplot(projection="3d")
        for si, s in enumerate(shapes):
            m = owner[:show] == si
            ax.scatter(*P[:show][m].T, s=1, color=s["color"])
        ax.set_xlim(box_lo[0], box_hi[0]); ax.set_ylim(box_lo[1], box_hi[1]); ax.set_zlim(box_lo[2], box_hi[2])
        ax.set_box_aspect(box_hi - box_lo)
        ax.set_xlabel("x"); ax.set_ylabel("y"); ax.set_zlabel("z")
    for s in shapes:
        ax.plot([], [], color=s["color"], lw=3, label=s["label"])
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title(f"Run 1: {show:,} of {n:,} points" + (" (outside points hidden)" if dim == 3 else ""))

    # 2. convergence of Estimate/True
    fig2, ax2 = plt.subplots(figsize=(9, 5.5))
    j = np.arange(1, n + 1)
    start = 10                                     # skip the first few wild estimates
    for si, s in enumerate(shapes):
        for r in range(runs):
            ax2.plot(j[start:], all_running[r, si, start:], color=s["color"],
                     lw=1.4 if runs == 1 else 0.6, alpha=1 if runs == 1 else 0.25)
        p = s["true"] / box_vol                    # theoretical 95% band
        if p < 1:
            band = 1.96 * np.sqrt((1 - p) / (p * j[start:]))
            ax2.plot(j[start:], 1 + band, color=s["color"], ls="--", lw=1)
            ax2.plot(j[start:], 1 - band, color=s["color"], ls="--", lw=1)
        ax2.plot([], [], color=s["color"], lw=2, label=s["label"])
    ax2.plot([], [], color="gray", ls="--", label="theory 95% band")
    ax2.axhline(1, color="black", lw=1)
    ax2.set_xscale("log")
    ax2.set_ylim(0.5, 1.5)
    ax2.set_xlabel("number of points (log scale)")
    ax2.set_ylabel(f"estimated {word} / true {word}")
    ax2.set_title(f"Convergence toward 1 ({runs} run{'s' if runs > 1 else ''})")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)

    # 3. distribution of final estimates (only meaningful with several runs)
    if runs > 1:
        fig3, ax3 = plt.subplots(figsize=(9, 5))
        lo, hi = finals.min(), finals.max()
        bins = np.linspace(lo, hi, 26)
        for si, s in enumerate(shapes):
            ax3.hist(finals[:, si], bins=bins, histtype="step", lw=2, color=s["color"],
                     label=f"{s['label']}  (mean {finals[:, si].mean():.4f})")
        ax3.axvline(1, color="black", lw=1)
        ax3.set_xlabel(f"final estimated {word} / true {word}  (n = {n:,})")
        ax3.set_ylabel("number of runs")
        ax3.set_title(f"Final estimates across {runs} runs: should be centered on 1")
        ax3.legend(fontsize=8)

    for f in plt.get_fignums():
        plt.figure(f).tight_layout()


if __name__ == "__main__":
    main()
