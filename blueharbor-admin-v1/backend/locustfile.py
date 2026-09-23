from locust import HttpUser, task, between
import random

class BlueHarborUser(HttpUser):
    wait_time = between(1, 5)

    def on_start(self):
        # Optionally perform login here if testing authenticated routes
        pass

    @task(3)
    def view_catalog(self):
        self.client.get("/api/catalog")

    @task(1)
    def view_health(self):
        self.client.get("/api/health")

    # To test actual load on more complex endpoints, auth tokens would be needed
    # for full simulated behavior.
