# Monte Carlo Simulation: Learning the Basics

Estimating areas and volumes by throwing random points, and learning how to tell a real bug from ordinary statistical behavior.

This project is part of my work learning the basics of particle physics under the guidance of **Professor Ashot Gasparian**, North Carolina A&T State University. Monte Carlo methods show up everywhere in particle physics: simulating detectors, working out what fraction of particles a detector can see (its *acceptance*), and estimating uncertainties. Before using them on physics problems, I started with the simplest version: estimating the area of an ellipse inside a box.

![100 runs of the ellipse estimate](02-verification-100-runs/ellipse_100_runs.png)

---

## The idea

Throw `N` random points uniformly into a box of known area `A`. Count how many land inside the shape (`N_inside`).

```
estimated area = A × (N_inside / N)
```

As `N` grows, the estimate should approach the true area, so **estimate / true area → 1**.

---

## My journey

The repo is laid out in the order the work happened. Each folder has its own README.

| Step | Folder | What happened |
|---|---|---|
| 1 | [`01-original-ellipse/`](01-original-ellipse/) | My first script: an ellipse in a rectangle, with the running estimate plotted as points are added. |
| 2 | [`02-verification-100-runs/`](02-verification-100-runs/) | Professor Gasparian questioned my graphs. I ran the method 100 times to check whether my calculation was wrong. |
| 3 | [`03-multi-shape-2d-3d/`](03-multi-shape-2d-3d/) | With the method checked, I generalized it: several shapes, 2D or 3D, and many independent runs. |
| 4 | [`04-interactive-ui/`](04-interactive-ui/) | An interactive version: drag shapes around, change the number of points, and watch the estimate converge. |

### What my professor asked me to verify

When I showed my first plots, Professor Gasparian pointed out two things:

1. **The estimate seemed to drift or "skew" away from 1** as the number of points grew, when it should be converging to 1.
2. **The shape of the plots didn't look random enough.** He expected the estimates to scatter more randomly.

He asked me to find out whether **something was wrong with how I was calculating**, or whether it was **just the nature of the random number generator and the shape and size of the ellipse**.

### What I found

I reran exactly the same calculation 100 times, with 10,000 points each ([step 2](02-verification-100-runs/)):

- **The calculation was correct.** The 100 final estimates averaged **0.9994** of the true area, with a spread of 0.015 (theory predicts 0.017). 45 runs ended above 1 and 55 below. The estimator is unbiased.
- **There was a real plotting bug.** My convergence plot drew the *raw area* `S` against a reference line at `y = 1`. It should have plotted `S / E` (estimate ÷ true area). Unless the ellipse's area happened to be 1, the plot could never sit on the line.
- **The "skew" was not a real effect.** I was computing mean, variance and skewness over the *running estimates within a single run*. Those numbers are not independent: each one reuses all the points before it. Across 100 runs, that "skew" ranged from −18 to +56, with no consistent sign. It was noise.
- **A single run naturally stays on one side of 1.** Because each running estimate includes every earlier point, one early streak pushes the whole path to one side, and it then closes in slowly. This is a known result, the **arcsine law**. In 42 of the 100 runs, the estimate spent more than 90% (or less than 10%) of its time above 1. This is what made the plots look "not random". The behavior is real but expected; it isn't an error.
- **The early plot has visible patterns because the count is a whole number.** With `j` points, the estimate can only take the values `A·m/j`, where `m` is the number of points inside. At small `j`, this lines the points up along smooth curves.

### Conclusion

The Monte Carlo calculation was right. The drift came from how running averages behave, plus one plotting mistake. The right way to check a Monte Carlo estimator is to run it **many independent times** and look at the spread of the **final** results. That spread shrinks like **1/√N**:

```
standard error of (estimate / true) = sqrt( (1 − p) / (p · N) ),   where p = shape area / box area
```

---

## What I learned

- **How hit-or-miss Monte Carlo works,** and why its error shrinks like `1/√N`. To make it 10× more precise, you need 100× more points.
- **Plot what you mean to compare.** If the reference line is at 1, the data must be a ratio.
- **One run is not a distribution.** Statistics computed along a single running average describe that one path, not the estimator.
- **Random doesn't mean jittery.** A cumulative average is smooth and can stay on one side of the true value for a long time. That is the arcsine law, not a bad random number generator.
- **The box matters.** The smaller the shape is compared to the box (small `p`), the noisier the estimate. If the shape sticks out of the box, the estimate converges to the wrong answer (below 1).
- **The connection to physics:** counting the fraction of random events that fall inside a region is the same idea used to estimate a detector's geometric acceptance. The `1/√N` uncertainty is the same counting statistics that appear in real experiments.

---

## Running the code

Requires Python 3 with:

```bash
pip install -r requirements.txt
```

The interactive UI also needs `tkinter`. On Ubuntu/Debian: `sudo apt install python3-tk`.

```bash
python3 01-original-ellipse/ellipse_area.py          # original (interactive prompts)
python3 02-verification-100-runs/ellipse_100_runs.py  # 100-run verification, saves the figure
python3 03-multi-shape-2d-3d/monte_carlo_shapes.py    # many shapes, 2D/3D, many runs (terminal)
python3 04-interactive-ui/monte_carlo_ui.py           # drag-and-drop UI
```

---

## Acknowledgments

Thanks to **Professor Ashot Gasparian** (North Carolina A&T State University) for his guidance. He asked the right questions about my results and pushed me to verify them rather than accept them.
