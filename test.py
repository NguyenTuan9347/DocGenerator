"""
math_utils.py

This module provides basic mathematical utility functions, including operations
such as computing square roots and powers. It demonstrates common uses of
docstrings in Python for modules, classes, and functions.
"""

import math


class MathUtils:
    """
    A utility class for basic mathematical operations.
    """

    def __init__(self):
        """
        Initialize the MathUtils instance.
        This class currently does not maintain any state.
        """
        pass

    def compute_sqrt(self, x):
        """
        Compute the square root of a non-negative number.

        Parameters:
        x (float): The number to compute the square root of. Must be >= 0.

        Returns:
        float: The square root of the input number.

        Raises:
        ValueError: If x is negative.
        """
        if x < 0:
            raise ValueError("Cannot compute square root of a negative number.")
        return math.sqrt(x)

    def compute_pow(self, base, exponent):
        """
        Compute the result of raising a number to a power.

        Parameters:
        base (float): The base number.
        exponent (float): The exponent to raise the base to.

        Returns:
        float: The result of base raised to the power of exponent.
        """
        return math.pow(base, exponent)


def example_usage():
    """
    Demonstrate usage of the MathUtils class.
    """
    mu = MathUtils()
    print("Square root of 25:", mu.compute_sqrt(25))
    print("2 raised to power 5:", mu.compute_pow(2, 5))


# Script entry point
if __name__ == "__main__":
    example_usage()
