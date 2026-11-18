from fastapi import APIRouter

from app.api.analysis import router as analysis_router
from app.api.analysis_advanced import router as advanced_analysis_router
from app.api.analysis_derivatives import router as liquidation_router
from app.api.analysis_intelligence import router as intelligence_router
from app.api.analysis_order_book import router as order_book_router
from app.api.analysis_evaluation import router as evaluation_router
from app.api.agent_analysis import router as agent_analysis_router
from app.api.backtest import router as backtest_router
from app.api.health import router as health_router
from app.api.devices import router as devices_router
from app.api.market import router as market_router
from app.api.order_flow import router as order_flow_router
from app.api.signals import router as signals_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(devices_router)
api_router.include_router(market_router)
api_router.include_router(agent_analysis_router)
api_router.include_router(analysis_router)
api_router.include_router(advanced_analysis_router)
api_router.include_router(order_flow_router)
api_router.include_router(intelligence_router)
api_router.include_router(order_book_router)
api_router.include_router(liquidation_router)
api_router.include_router(backtest_router)
api_router.include_router(evaluation_router)
api_router.include_router(signals_router)
