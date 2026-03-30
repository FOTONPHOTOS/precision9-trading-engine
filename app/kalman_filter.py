"""
Kalman Filter Utility
=====================

A simple, reusable 1D Kalman Filter for smoothing noisy data streams
like price, indicators, or confidence scores.

Author: Arsenal Trading System - Advanced Signal Processing
"""

import numpy as np

class KalmanFilter:
    """
    A simple 1D Kalman filter.
    """
    def __init__(self, process_variance, measurement_variance, initial_value=0.0, initial_estimate_error=1.0):
        """
        Initialize the Kalman Filter.

        Args:
            process_variance (float): The variance of the process noise (Q).
                                      Controls how much the state is expected to change.
                                      Higher Q = more responsive, less smooth.
            measurement_variance (float): The variance of the measurement noise (R).
                                          Controls how much the measurement is trusted.
                                          Higher R = less trust in measurement, more smooth.
            initial_value (float): The initial value for the state.
            initial_estimate_error (float): The initial estimate error covariance (P).
        """
        self.q = process_variance
        self.r = measurement_variance
        self.p = initial_estimate_error
        self.x = initial_value  # The filtered value (state)

    def update(self, measurement):
        """
        Update the filter with a new measurement.

        Args:
            measurement (float): The new measurement.

        Returns:
            float: The updated, filtered value.
        """
        # Prediction update
        self.p = self.p + self.q

        # Measurement update
        k = self.p / (self.p + self.r)  # Kalman gain
        self.x = self.x + k * (measurement - self.x)
        self.p = (1 - k) * self.p

        return self.x

    def set_process_variance(self, process_variance):
        """Dynamically set the process variance (Q)."""
        self.q = process_variance

    def set_measurement_variance(self, measurement_variance):
        """Dynamically set the measurement variance (R)."""
        self.r = measurement_variance
