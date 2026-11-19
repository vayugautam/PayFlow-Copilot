from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


def _nonce(request: Request) -> str:
    nonce = getattr(request.state, "csp_nonce", None)
    if not nonce:
        raise RuntimeError("Missing CSP nonce for documentation page")
    return nonce


@router.get("/docs", include_in_schema=False)
async def swagger_ui(request: Request) -> HTMLResponse:
    nonce = _nonce(request)
    title = request.app.title
    html = f"""<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{title} - Swagger UI</title>
    <link rel=\"stylesheet\" href=\"/static/docs/swagger-ui/swagger-ui.css\" />
    <style nonce=\"{nonce}\">html {{ box-sizing: border-box; overflow-y: scroll; }} *, *:before, *:after {{ box-sizing: inherit; }} body {{ margin: 0; background: #fafafa; }}</style>
  </head>
  <body>
    <div id=\"swagger-ui\"></div>
    <script src=\"/static/docs/swagger-ui/swagger-ui-bundle.js\"></script>
    <script nonce=\"{nonce}\">
      window.onload = function() {{
        window.ui = SwaggerUIBundle({{
          url: '/openapi.json',
          dom_id: '#swagger-ui',
          deepLinking: true,
          presets: [SwaggerUIBundle.presets.apis],
          layout: 'BaseLayout'
        }});
      }};
    </script>
  </body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/redoc", include_in_schema=False)
async def redoc_ui(request: Request) -> HTMLResponse:
    nonce = _nonce(request)
    title = request.app.title
    html = f"""<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{title} - ReDoc</title>
    <style nonce=\"{nonce}\">body {{ margin: 0; padding: 0; }}</style>
  </head>
  <body>
    <redoc spec-url=\"/openapi.json\"></redoc>
    <script src=\"/static/docs/redoc/redoc.standalone.js\"></script>
  </body>
</html>"""
    return HTMLResponse(content=html)
