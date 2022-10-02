class CORSMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (request.path or "").startswith("/api/"):
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Methods"] = "*"
            response["Access-Control-Allow-Headers"] = "authorization"
            response["Access-Control-Max-Age"] = 600

        return response
