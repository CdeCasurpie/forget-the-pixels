import numpy as np
a = np.array([0.0, 20.0])
n = np.array([0.0, 1.0])
t = np.array([1.0, 0.0])
u1, u2 = 0.0, 0.25
w1, w2 = -0.20, 0.0
for u, w in [(u1, w1), (u2, w1), (u2, w2), (u1, w2)]:
    print(a + u*t + w*n)
