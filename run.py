from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi import Request
from urllib.parse import quote

from backend.config.settings import Settings
from backend.auth import AuthManager, protected_path
from backend.routes.screener import router as screener_router
from backend.routes.stocks import router as stocks_router
from backend.routes.stock_pedigree import router as stock_pedigree_router
from backend.routes.stock_supplemental import router as stock_supplemental_router
from backend.routes.stock_market_cap import router as stock_market_cap_router
from backend.routes.insights import router as insights_router
from backend.routes.portfolio import router as portfolio_router
from backend.routes.stock_portfolio_benchmarks import router as stock_portfolio_benchmarks_router
from backend.routes.mutual_funds import router as mutual_funds_router
from backend.routes.bonds import router as bonds_router

settings = Settings()
auth = AuthManager(settings)

app = FastAPI(
    title="Market Analysis API",
    description="Indian stock-market analysis with screening, fundamentals, portfolio analysis, and AI insights.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FAVICON_URL = "/static/images/hero-market-analysis.png?v=20261006"

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sign in · Market Analysis</title>
<meta name="theme-color" content="#071225">
<meta property="og:title" content="Market Analysis">
<meta property="og:description" content="A comprehensive platform for capital market analysis covering stocks, mutual funds and bonds.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://market-analysis-g4ow.onrender.com/">
<meta property="og:image" content="https://market-analysis-g4ow.onrender.com/static/images/market-analysis-og.jpg?v=20261009">
<meta property="og:image:secure_url" content="https://market-analysis-g4ow.onrender.com/static/images/market-analysis-og.jpg?v=20261009">
<meta property="og:image:alt" content="Market Analysis">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:image:width" content="300">
<meta property="og:image:height" content="158">
<meta property="og:site_name" content="Market Analysis">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Market Analysis">
<meta name="twitter:description" content="A comprehensive platform for capital market analysis covering stocks, mutual funds and bonds.">
<meta name="twitter:image" content="https://market-analysis-g4ow.onrender.com/static/images/market-analysis-og.jpg?v=20261009">
<meta name="twitter:image:alt" content="Market Analysis">
<style>
*{box-sizing:border-box}html,body{margin:0;min-height:100%;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#071225;color:#fff}
body{display:grid;place-items:center;overflow:hidden;position:relative}
body:before{content:"";position:fixed;inset:-30%;background:radial-gradient(circle at 25% 25%,rgba(37,99,235,.32),transparent 30%),radial-gradient(circle at 80% 70%,rgba(124,58,237,.26),transparent 30%),radial-gradient(circle at 50% 100%,rgba(6,182,212,.16),transparent 35%);filter:blur(12px);animation:ambient 12s ease-in-out infinite alternate}
@keyframes ambient{from{transform:scale(1) rotate(0deg)}to{transform:scale(1.08) rotate(3deg)}}
.login-stage{width:min(94vw,520px);position:relative;z-index:2}
.login-card{position:relative;overflow:hidden;border:1px solid rgba(255,255,255,.18);border-radius:30px;padding:34px 32px 30px;background:linear-gradient(145deg,rgba(255,255,255,.15),rgba(255,255,255,.055));box-shadow:0 35px 100px rgba(0,0,0,.45),inset 0 1px rgba(255,255,255,.18);backdrop-filter:blur(28px)}
.orbit,.orbit:before,.orbit:after{position:absolute;border:1px solid rgba(125,211,252,.18);border-radius:50%;pointer-events:none}.orbit{width:420px;height:420px;right:-190px;top:-210px;animation:spin 18s linear infinite}.orbit:before{content:"";inset:32px}.orbit:after{content:"";inset:78px;border-color:rgba(167,139,250,.22)}@keyframes spin{to{transform:rotate(360deg)}}
.brand{display:flex;align-items:center;gap:14px;position:relative;z-index:1}.brand-mark{width:54px;height:54px;border-radius:17px;display:grid;place-items:center;background:linear-gradient(135deg,#2563eb,#7c3aed);box-shadow:0 12px 30px rgba(37,99,235,.35);font-size:25px;font-weight:900}.eyebrow{text-transform:uppercase;letter-spacing:.16em;font-size:10px;color:#93c5fd;font-weight:800}.brand h1{margin:3px 0 0;font-size:24px;letter-spacing:-.04em}.title{margin:38px 0 8px;font-size:34px;letter-spacing:-.055em}.subtitle{margin:0 0 28px;color:#b7c4d8;line-height:1.55}
label{display:block;font-size:12px;font-weight:800;color:#dbeafe;margin:0 0 8px}.field{margin-bottom:17px}.input{width:100%;height:52px;border:1px solid rgba(255,255,255,.16);border-radius:14px;background:rgba(4,12,27,.48);color:#fff;padding:0 16px;font-size:16px;outline:none;transition:.2s}.input:focus{border-color:#60a5fa;box-shadow:0 0 0 4px rgba(96,165,250,.12)}
.submit{width:100%;height:54px;border:0;border-radius:15px;background:linear-gradient(100deg,#2563eb,#4f46e5 55%,#7c3aed);color:#fff;font-size:16px;font-weight:850;cursor:pointer;box-shadow:0 16px 30px rgba(37,99,235,.28);transition:transform .2s,box-shadow .2s}.submit:hover{transform:translateY(-2px);box-shadow:0 20px 38px rgba(37,99,235,.38)}.submit:disabled{opacity:.65;cursor:wait;transform:none}
.message{min-height:22px;margin:15px 0 0;color:#fca5a5;font-size:13px;font-weight:650}.secure{margin-top:22px;text-align:center;color:#8ea0b8;font-size:11px}.secure span{color:#86efac}
@media(max-width:520px){.login-card{padding:28px 22px;border-radius:25px}.title{font-size:30px}.orbit{right:-250px}}
</style>
</head>
<body>
<main class="login-stage">
<section class="login-card">
<div class="orbit"></div>
<div class="brand"><div class="brand-mark">M</div><div><div class="eyebrow">Private access</div><h1>Market Analysis</h1></div></div>
<h2 class="title">Welcome back.</h2>
<p class="subtitle">Sign in to access the complete Market Analysis application, including stocks, portfolios, mutual funds and bonds.</p>
<form id="login-form" autocomplete="on">
<div class="field"><label for="username">Username</label><input class="input" id="username" name="username" autocomplete="username" required autofocus></div>
<div class="field"><label for="password">Password</label><input class="input" id="password" name="password" type="password" autocomplete="current-password" required></div>
<button class="submit" id="submit" type="submit">Sign in securely</button>
<div class="message" id="message" role="alert"></div>
</form>
<div class="secure">🔒 <span>Protected session</span> · Market Analysis private application</div>
</section>
</main>
<script>
const form=document.getElementById("login-form"),btn=document.getElementById("submit"),msg=document.getElementById("message");
const params=new URLSearchParams(location.search); const next=params.get("next")||"/";
form.addEventListener("submit",async e=>{
 e.preventDefault(); btn.disabled=true; btn.textContent="Signing in…"; msg.textContent="";
 try{
  const res=await fetch("/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},credentials:"same-origin",body:JSON.stringify({username:form.username.value,password:form.password.value,next})});
  const data=await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data.detail||"Unable to sign in.");
  location.href=data.redirect||"/";
 }catch(err){msg.textContent=err.message||"Unable to sign in.";btn.disabled=false;btn.textContent="Sign in securely";}
});
</script>
</body>
</html>"""

def auth_floating_controls(html: str) -> str:
    control = r'''
<style id="market-auth-ui">
#market-auth-float{position:fixed;right:18px;top:18px;z-index:2147483000;display:flex;align-items:center;gap:9px;padding:7px 9px 7px 13px;border:1px solid rgba(255,255,255,.5);border-radius:999px;background:rgba(8,18,38,.78);color:#fff;box-shadow:0 10px 30px rgba(0,0,0,.18);backdrop-filter:blur(18px);font:700 12px/1 system-ui,sans-serif}
#market-auth-float .dot{width:8px;height:8px;border-radius:50%;background:#4ade80;box-shadow:0 0 12px rgba(74,222,128,.9)}
#market-auth-float button{border:0;border-radius:999px;padding:8px 12px;background:rgba(255,255,255,.12);color:#fff;font-weight:800;cursor:pointer}
#market-auth-expired{display:none;position:fixed;inset:0;z-index:2147483001;place-items:center;background:rgba(3,9,20,.66);backdrop-filter:blur(12px);padding:24px}
#market-auth-expired .card{width:min(92vw,420px);padding:30px;border:1px solid rgba(255,255,255,.2);border-radius:26px;background:rgba(15,27,49,.94);color:#fff;text-align:center;box-shadow:0 30px 90px rgba(0,0,0,.45)}
#market-auth-expired h2{margin:0 0 8px;font:800 25px/1.15 system-ui,sans-serif}
#market-auth-expired p{color:#aebdd0;line-height:1.5;margin:0 0 22px}
#market-auth-expired a{display:block;padding:13px;border-radius:13px;background:linear-gradient(100deg,#2563eb,#7c3aed);color:#fff;text-decoration:none;font-weight:850}
@media(max-width:600px){#market-auth-float{top:auto;bottom:104px;right:16px}}
</style>
<div id="market-auth-float"><span class="dot"></span><span>Private access</span><button type="button" id="market-auth-logout">Sign out</button></div>
<div id="market-auth-expired"><div class="card"><h2>Session expired</h2><p>Your Market Analysis session has expired. Sign in again to continue.</p><a id="market-auth-relogin" href="/login">Sign in again</a></div></div>
<script>
(()=>{const logout=document.getElementById("market-auth-logout"),expired=document.getElementById("market-auth-expired");
 logout?.addEventListener("click",async()=>{try{await fetch("/api/auth/logout",{method:"POST",credentials:"same-origin"})}finally{location.href="/login?logged_out=1"}});
 const originalFetch=window.fetch.bind(window);
 window.fetch=async(...args)=>{const response=await originalFetch(...args);const input=args[0];const url=typeof input==="string"?input:(input&&input.url)||"";if(response.status===401&& !url.includes("/api/auth/")){expired.style.display="grid";const relog=document.getElementById("market-auth-relogin");if(relog)relog.href="/login?next="+encodeURIComponent(location.pathname+location.search)}return response};
})();
</script>
'''
    return html.replace("</body>", control + "</body>") if "</body>" in html else html + control

@app.middleware("http")
async def authentication_gate(request: Request, call_next):
    path = request.url.path
    if not protected_path(path):
        return await call_next(request)

    if auth.current_user(request):
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            # Middleware cannot safely consume/rebuild arbitrary streaming
            # responses. The application HTML routes are normal HTMLResponse
            # objects, so inject the floating authenticated access control there.
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            headers = dict(response.headers)
            headers.pop("content-length", None)
            html = body.decode("utf-8")
            html = auth_floating_controls(html)
            return HTMLResponse(content=html, status_code=response.status_code, headers=headers, media_type="text/html")
        return response

    if path.startswith("/api/"):
        return JSONResponse({"detail": "Authentication required."}, status_code=401)

    target = path + (("?" + request.url.query) if request.url.query else "")
    return RedirectResponse(url="/login?next=" + quote(target, safe=""), status_code=303)


def render_html_page(path: str) -> HTMLResponse:
    """Serve HTML with the Market Analysis artwork as the only site icon."""
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("/static/images/favicon.ico", FAVICON_URL)
    html = html.replace("/favicon.ico", FAVICON_URL)
    return HTMLResponse(content=html)


# Serve frontend HTML pages

@app.get("/login", include_in_schema=False)
async def login_page(request: Request):
    if auth.current_user(request):
        return RedirectResponse(url="/", status_code=303)
    return HTMLResponse(LOGIN_PAGE)


@app.post("/api/auth/login", include_in_schema=False)
async def login(request: Request):
    payload = await request.json()
    token, error, status = auth.login(
        request,
        str(payload.get("username", "")),
        str(payload.get("password", "")),
    )
    if error:
        return JSONResponse({"detail": error}, status_code=status)
    response = JSONResponse({"ok": True, "redirect": auth._safe_next(payload.get("next"))})
    response.set_cookie(value=token, **auth.cookie_kwargs())
    return response


@app.post("/api/auth/logout", include_in_schema=False)
async def logout(request: Request):
    if not auth.same_origin(request):
        return JSONResponse({"detail": "Invalid logout origin."}, status_code=403)
    auth.logout(request)
    response = JSONResponse({"ok": True})
    response.delete_cookie(**auth.clear_cookie_kwargs())
    return response

@app.get("/")
async def read_root(request: Request):
    # Keep the site root publicly readable as a login/preview surface. This is
    # important for link-preview crawlers (including WhatsApp), which may not
    # follow the authentication redirect before parsing Open Graph metadata.
    # The actual application HTML and every application API remain protected.
    if not auth.current_user(request):
        return HTMLResponse(LOGIN_PAGE)

    html = render_html_page("frontend/html/index.html").body.decode("utf-8")
    hero_url = "https://market-analysis-g4ow.onrender.com/static/images/hero-market-analysis.png?v=20261006"
    html = html.replace(
        'https://wsrv.nl/?url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fabmullick%2FMarket-Analysis%40main%2Fstatic%2Fimages%2Fhero-market-analysis.png&amp;w=1200&amp;h=630&amp;fit=cover&amp;output=jpg',
        hero_url,
    )
    html = html.replace(
        'https://cdn.jsdelivr.net/gh/abmullick/Market-Analysis@main/static/images/hero-market-analysis.png?v=20261005',
        '/static/images/hero-market-analysis.png?v=20261006',
    )
    return HTMLResponse(content=html)


@app.get("/stocks.html")
async def read_stocks():
    return render_html_page("frontend/html/stocks.html")


@app.get("/portfolio.html")
async def read_portfolio():
    return render_html_page("frontend/html/portfolio.html")


@app.get("/stock-portfolio-builder.html")
async def read_stock_portfolio_builder():
    return render_html_page("frontend/html/stock-portfolio-builder.html")


@app.get("/portfolio-builder.html")
async def read_portfolio_builder():
    return render_html_page("frontend/html/portfolio-builder.html")


@app.get("/portfolio-select-funds.html")
async def read_portfolio_select_funds():
    return render_html_page("frontend/html/portfolio-select-funds.html")


@app.get("/mutual-funds.html")
async def read_mutual_funds():
    return render_html_page("frontend/html/mutual-funds.html")


@app.get("/help.html")
async def read_help():
    return render_html_page("frontend/html/help.html")


@app.get("/bond-analysis.html")
async def read_bond_analysis():
    return render_html_page("frontend/html/bond-analysis.html")


@app.get("/og-preview-20261006.png")
async def og_preview_image():
    return FileResponse(
        "static/images/hero-market-analysis.png",
        media_type="image/png",
        headers={
            "Cache-Control": "no-cache, must-revalidate",
            "Content-Disposition": "inline",
        },
    )


@app.get("/static/images/hero-market-analysis.png")
async def social_preview_image():
    return FileResponse(
        "static/images/hero-market-analysis.png",
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )

# Serve static assets
app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(screener_router, prefix="/api/stocks", tags=["stocks"])
# Must precede the generic /{symbol} route in stocks_router.
app.include_router(stock_pedigree_router, prefix="/api/stocks", tags=["stocks"])
app.include_router(stocks_router, prefix="/api/stocks", tags=["stocks"])
app.include_router(stock_supplemental_router, prefix="/api/stocks", tags=["stocks"])
app.include_router(stock_market_cap_router, prefix="/api/stocks", tags=["stocks"])
app.include_router(portfolio_router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(stock_portfolio_benchmarks_router, prefix="/api/stock-benchmarks", tags=["stock-benchmarks"])
app.include_router(mutual_funds_router, prefix="/api/mutual-funds", tags=["mutual-funds"])
app.include_router(insights_router, prefix="/api/insights", tags=["insights"])
app.include_router(bonds_router, prefix="/api/bonds", tags=["bonds"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "run:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_debug,
    )
