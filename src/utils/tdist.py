import math

EPSILON = 1e-14
MAX_ITERATIONS = 500
TINY = 1e-300
BISECTION_ITERATIONS = 200
BISECTION_TOLERANCE = 1e-13


def _non_zero(value: float) -> float:
    """
    Returns the value, or TINY when it is too close to zero to divide by.
    """
    return value if abs(value) > TINY else TINY


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """
    Evaluates the continued fraction of the incomplete beta function with the modified Lentz method.
    """
    qab, qap, qam = a + b, a + 1.0, a - 1.0

    # First step of the fraction
    c = 1.0
    d = 1.0 / _non_zero(1.0 - qab * x / qap)
    h = d

    # Iterate until the correction factor is 1 within EPSILON
    for m in range(1, MAX_ITERATIONS + 1):
        m2 = 2 * m
        for term in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 / _non_zero(1.0 + term * d)
            c = _non_zero(1.0 + term / c)
            delta = d * c
            h *= delta
        if abs(delta - 1.0) < EPSILON:
            break

    return h


def _regularized_beta(a: float, b: float, x: float) -> float:
    """
    Returns the regularized incomplete beta function I_x(a, b).
    """
    # Outside (0, 1) the function is constant
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
    # Reject input the distribution is not defined for
    if not 0.0 < probability < 1.0:
        raise ValueError("probability must be between 0 and 1")
    if df <= 0:
        raise ValueError("df must be positive")

    # The median is 0 and the lower half mirrors the upper half
    if probability == 0.5:
        return 0.0
    if probability < 0.5:
        return -t_ppf(1.0 - probability, df)

    # Grow the upper bound until it passes the target
    low, high = 0.0, 1.0
    while t_cdf(high, df) < probability:
        low, high = high, high * 2.0

    # Halve the bracket until it is narrower than the tolerance
    for _ in range(BISECTION_ITERATIONS):
        mid = (low + high) / 2.0
        if t_cdf(mid, df) < probability:
            low = mid
        else:
            high = mid
        if high - low < BISECTION_TOLERANCE * max(1.0, high):
            break

    return (low + high) / 2.0
