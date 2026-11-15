from fastapi import APIRouter
from app.api.analysis import router as analysis_router
from app.api.analysis_advanced import router as advanced_analysis_router
from app.api.backtest import router as backtest_router
from app.api.health import router as health_router
from app.api.market import router as market_router
from app.api.order_flow import router as order_flow_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(market_router)
api_router.include_router(analysis_router)
api_router.include_router(advanced_analysis_router)
api_router.include_router(order_flow_router)
api_router.include_router(backtest_router)
