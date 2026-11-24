import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Rectangle
import numpy as np
from scipy.spatial import ConvexHull
from scipy.stats import skew

print(f'choose shape:{"circle", "square", "triangle", "ellipse"}')

if input() == "ellipse":

    # rectangle/square
    hb = float(input("h (center x of box): "))
    kb = float(input("k (center y of box): "))
    w = float(input("width of box: "))
    ht = float(input("height of box: "))

    # Puts random points in the rectangle
    n = int(input("number of points: "))
    x = np.random.uniform(hb - w/2, hb + w/2, n)
    y = np.random.uniform(kb - ht/2, kb + ht/2, n)

    fig, ax = plt.subplots()

    # Plots the random points in the rectangle
    ax.scatter(x, y, s=1)

    h = float(input("h (center x of ellipse): "))
    k = float(input("k (center y of ellipse): "))
    a = float(input("a (semi-major axis): "))
    b = float(input("b (semi-minor axis): "))

    # ellipse
    ax.add_patch(Ellipse((h, k), 2*b, 2*a, fill=False))
    # rectangle
    ax.add_patch(Rectangle((hb-w/2, kb-ht/2), w, ht, fill=False))
    ax.set_aspect('equal')

    # finds points inside the ellipse
    i = ((x-h)**2)/(b**2) + ((y-k)**2)/(a**2)<=1

    #puts points inside the ellipse in a new array
    points = np.column_stack([x[i], y[i]])
    areas = []
    #j=3 because the first two points are not enough to form a triangle, so we start with 3 points
    j=3

    A = w * ht
    E = np.pi * a * b

    # finds the cumulative sum of the points inside the ellipse
    inside = np.cumsum(i.astype(int))

    #j is the total number of points, S is the estimated area of the ellipse
    j = 1
    #[j-1] is the number of points inside the ellipse, inside is the cumulative sum, A is the area of the rectangle, and E is the area of the ellipse
    estimates = []
    while j <= n:
        S = (A * (inside [j-1]/ j)) # estimated area of the ellipse
        plt.figure(2)

        # plots a scatter plot of the estimated area of the ellipse as a function of the number of points 
        plt.scatter(j, S, color='blue', s=1)
        plt.axhline(y=1, color='r') 

        estimates.append(S/E)

        mean = np.mean(estimates)
        variance = np.var(estimates)

        if len(estimates) >= 3:
            skewness = skew(estimates)
        else:
            skewness = 0

        print("Points: " + str(j) +
            " | Mean: " + str(mean) +
            " | Variance: " + str(variance) +
            " | Skew: " + str(skewness))

        j += 1   

    plt.xlabel("Number of Points")
    plt.ylabel("Estimate Area/Real Area")

    plt.figure(3)
    plt.hist(estimates, bins=30)
    plt.axvline(x=1, color='red')
    plt.xlabel("Estimated area / Real area")
    plt.ylabel("Frequency")
    plt.title("Histogram of area estimates")
        
        
    EA = A * (len(points) / n)   
    
    A = np.pi * a * b
    print(f"Real area of ellipse: {A}")
    print(f"Estimated area of ellipse: {EA}")

plt.show()
