import math

EPSILON = 1e-14
MAX_ITERATIONS = 500
TINY = 1e-300


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """
    Evaluates the continued fraction of the incomplete beta function with the modified Lentz method.
    """
    qab, qap, qam = a + b, a + 1.0, a - 1.0

    # First step of the fraction
    c = 1.0
    d = 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > TINY else TINY)
    h = d

    # Iterate until the correction factor is 1 within EPSILON
    for m in range(1, MAX_ITERATIONS + 1):
        m2 = 2 * m
        for term in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + term * d
            d = 1.0 / (d if abs(d) > TINY else TINY)
            c = 1.0 + term / c
            c = c if abs(c) > TINY else TINY
            delta = d * c
            h *= delta
        if abs(delta - 1.0) < EPSILON:
            break
    return h


def _regularized_beta(a: float, b: float, x: float) -> float:
    """
    Returns the regularized incomplete beta function I_x(a, b).
    """
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0

    # Front factor, then the fraction on whichever side converges faster
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def t_cdf(t: float, df: float) -> float:
    """
    Returns P(T <= t) for Student's t distribution with df degrees of freedom.
    """
    tail = 0.5 * _regularized_beta(df / 2.0, 0.5, df / (df + t * t))
    return 1.0 - tail if t > 0 else tail


def t_ppf(probability: float, df: float) -> float:
    """
    Returns the t value whose cumulative probability is the given one (the inverse of t_cdf), found by bisection.
    """
    if not 0.0 < probability < 1.0:
        raise ValueError("probability must be between 0 and 1")
    if df <= 0:
        raise ValueError("df must be positive")
    if probability == 0.5:
        return 0.0
    if probability < 0.5:
        return -t_ppf(1.0 - probability, df)

    # Grow the upper bound until it passes the target, then halve the bracket
    low, high = 0.0, 1.0
    while t_cdf(high, df) < probability:
        low, high = high, high * 2.0
    for _ in range(200):
        mid = (low + high) / 2.0
        if t_cdf(mid, df) < probability:
            low = mid
        else:
            high = mid
        if high - low < 1e-13 * max(1.0, high):
            break
    return (low + high) / 2.0
