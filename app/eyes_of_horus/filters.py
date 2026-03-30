import numpy as np

class KalmanFilter:
    """
    A simple 1D Kalman filter for smoothing price data.
    """
    def __init__(self, process_variance, measurement_variance, initial_value=0.0):
        self.process_variance = process_variance
        self.measurement_variance = measurement_variance
        self.estimate = initial_value
        self.error_in_estimate = 1.0
        self.previous_estimate = initial_value

    def update(self, measurement):
        # Prediction
        self.error_in_estimate += self.process_variance

        # Update
        kalman_gain = self.error_in_estimate / (self.error_in_estimate + self.measurement_variance)
        self.previous_estimate = self.estimate
        self.estimate = self.estimate + kalman_gain * (measurement - self.estimate)
        self.error_in_estimate = (1.0 - kalman_gain) * self.error_in_estimate
        
        return self.estimate

    def get_velocity(self) -> float:
        """Returns the change since the last update, representing velocity."""
        return self.estimate - self.previous_estimate
