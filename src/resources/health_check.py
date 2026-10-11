from fastapi.responses import Response, JSONResponse
from controllers.health_controller import HealthController


class HealthCheckResource:
    def on_get_home(self):
        return JSONResponse({'service': 'banking-api'})

    def on_get_health_check(self):
        return Response(status_code=204)

    def on_get_readiness(self):
        HealthController('health').readiness()
        return Response(status_code=204)
