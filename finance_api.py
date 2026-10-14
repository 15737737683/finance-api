# -*- coding: utf-8 -*-
"""
finance_api.py
==============
将 financial_data_channels.py 封装为 HTTP 服务，供百度千帆「自定义工具-API接入」调用。

运行方式：
    pip install fastapi uvicorn
    uvicorn finance_api:app --host 0.0.0.0 --port 8000

关键：
    - FastAPI 会自动生成接口规范文档（/openapi.json），千帆 API 接入可一键导入；
    - 每个接口对应一个数据渠道（见 financial_data_channels.py 的渠道映射）；
    - 返回统一为 JSON：{ "ok": true, "data": <结果> } 或 { "ok": false, "error": <原因> }。
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import traceback
from typing import Any

from fastapi import FastAPI, HTTPException, Query

import financial_data_channels as f

app = FastAPI(
    title="金融数据获取渠道服务",
    description="覆盖上交所/深交所/北交所、东方财富、新浪财经、雪球、每日经济新闻、同花顺、行业研报等数据渠道",
    version="1.0.0",
)


def _sanitize(v: Any) -> Any:
    """把不可 JSON 序列化的值统一转成安全类型。"""
    if v is None or isinstance(v, (str, int, bool)):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, (_dt.date, _dt.datetime)):
        return v.isoformat()
    # 处理 pandas/numpy 常见类型
    name = type(v).__name__
    if "Timestamp" in name:
        return v.isoformat()
    if name in ("int64", "int32", "uint8", "uint16", "uint32", "uint64"):
        return int(v)
    if name in ("float64", "float32"):
        return v if math.isfinite(v) else None
    if name == "Decimal":
        return float(v)
    if isinstance(v, (list, tuple, set)):
        return [_sanitize(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _sanitize(x) for k, x in v.items()}
    # 兜底：尝试 str
    return str(v)


def _ok(data: Any) -> dict:
    if hasattr(data, "to_dict"):
        data = data.to_dict(orient="records")
    return {"ok": True, "data": _sanitize(data)}


def _run(fn) -> dict:
    try:
        return _ok(fn())
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.get("/")
def index():
    return {"service": "金融数据获取渠道服务", "docs": "/docs", "openapi": "/openapi.json"}


@app.get("/market")
def market(market: str = Query("全部A股", description="全部A股/沪市A股/深市A股/北交所A股")):
    """官方渠道——上交所/深交所/北交所市场行情概览（新浪指数源）。"""
    return _run(lambda: f.fetch_exchange_market(market))


@app.get("/announcement")
def announcement(symbol: str = Query("600519", description="股票代码")):
    """官方渠道——上市公司公告（交易所权威披露）。"""
    return _run(lambda: f.fetch_exchange_announcement(symbol))


@app.get("/eastmoney/financial")
def eastmoney_financial(symbol: str = Query("600519", description="股票代码")):
    """财经网站——东方财富财务摘要。"""
    return _run(lambda: f.fetch_eastmoney_financial(symbol))


@app.get("/eastmoney/quote")
def eastmoney_quote(symbol: str = Query("600519", description="股票代码")):
    """财经网站——东方财富个股基本信息/实时行情。"""
    return _run(lambda: f.fetch_eastmoney_quote(symbol))


@app.get("/eastmoney/spot")
def eastmoney_spot():
    """东方财富全A快照（新浪指数替代）。"""
    return _run(lambda: f.fetch_eastmoney_all_spot())


@app.get("/sina/history")
def sina_history(symbol: str = Query("sh600519", description="带交易所前缀，如sh600519"), period: str = Query("daily", description="daily/weekly/monthly")):
    """财经网站——新浪财经历史行情。"""
    return _run(lambda: f.fetch_sina_history(symbol, period))


@app.get("/xueqiu/quote")
def xueqiu_quote(symbol: str = Query("SH600519", description="大写前缀，如SH600519"), token: str | None = Query(None, description="雪球登录xq_a_token")):
    """财经网站——雪球实时行情（需登录token）。"""
    return _run(lambda: f.fetch_xueqiu_quote(symbol, token))


@app.get("/news")
def news(limit: int = Query(10, description="返回条数")):
    """财经网站——每日经济新闻。"""
    return _run(lambda: f.fetch_nbd_news(limit=limit))


@app.get("/ths/financial")
def ths_financial(symbol: str = Query("600519", description="股票代码")):
    """证券软件——同花顺财务摘要。"""
    return _run(lambda: f.fetch_ths_financial(symbol))


@app.get("/research")
def research(symbol: str = Query("600519", description="股票代码")):
    """辅助渠道——行业研究报告。"""
    return _run(lambda: f.fetch_research_report(symbol))


@app.get("/company")
def company(symbol: str = Query("600519", description="股票代码")):
    """辅助渠道——上市公司基本信息。"""
    return _run(lambda: f.fetch_company_info(symbol))
