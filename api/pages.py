from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# 创建路由器
router = APIRouter()

# 模板配置
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    return templates.TemplateResponse(request=request, name="config.html")

@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    return templates.TemplateResponse(request=request, name="logs.html")

@router.get("/keys", response_class=HTMLResponse)
async def keys_page(request: Request):
    return templates.TemplateResponse(request=request, name="keys.html")

@router.get("/api-example", response_class=HTMLResponse)
async def api_example_page(request: Request):
    return templates.TemplateResponse(request=request, name="api-example.html")
