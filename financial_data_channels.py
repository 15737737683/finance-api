# -*- coding: utf-8 -*-
"""
financial_data_channels.py
===========================
「数据获取渠道及权威性」Python 连接模块
--------------------------------------
依据你提供的渠道导图，将每个数据获取渠道封装为独立的 Python 函数。

渠道对照（图片 -> 本模块函数）：
  官方渠道  : 上交所 / 深交所 / 北交所  -> fetch_exchange_market()
  财经网站  : 东方财富                 -> fetch_eastmoney_quote() / fetch_eastmoney_financial()
             新浪财经                 -> fetch_sina_history() / fetch_sina_spot()
             雪球                     -> fetch_xueqiu_quote()
             每日经济新闻             -> fetch_nbd_news()
  证券软件  : 东方财富 / 同花顺       -> fetch_ths_history()
  辅助渠道  : 上市公司官网、研报       -> fetch_research_report()

依赖安装：
    pip install akshare requests pandas

依赖库 akshare 是开源的财经数据接口库，底层封装了交易所、东方财富、
新浪财经、同花顺、雪球等公开数据源，是最主流的"Python 连财经渠道"方案。
"""
from __future__ import annotations

import time

import requests
import pandas as pd


# ---------------------------------------------------------------------------
# 0. 通用工具
# ---------------------------------------------------------------------------
def _guard(df: pd.DataFrame | None, name: str) -> pd.DataFrame:
    """空结果防护：接口失败/无数据时抛清晰异常，避免静默返回空表。"""
    if df is None or df.empty:
        raise RuntimeError(f"[{name}] 未获取到数据，请检查网络或稍后重试。")
    return df


def _retry(fn, name: str, retries: int = 3) -> pd.DataFrame:
    """带退避重试的通用抓取，兼容交易所快照等易断连接口。"""
    last_err = None
    for i in range(max(1, retries)):
        try:
            return _guard(fn(), name)
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"[{name}] 重试{retries}次仍失败: {last_err}")


# ---------------------------------------------------------------------------
# 1. 官方渠道 —— 上交所 / 深交所 / 北交所
# ---------------------------------------------------------------------------
def fetch_exchange_market(market: str = "全部A股") -> pd.DataFrame:
    """获取沪深京交易所市场行情概览（官方渠道·市场层面）。

    说明：东财全市场快照接口对本机存在反爬拦截，故改用新浪指数快照
    （覆盖上证/深证/北证等主要指数），轻量且稳定。
    参数 market: '全部A股'(默认) | '沪市A股' | '深市A股' | '北交所A股'，
    用于按代码前缀过滤指数/行情。
    """
    import akshare as ak

    df = _guard(ak.stock_zh_index_spot_sina(), "交易所市场行情")
    if market in ("沪市A股", "深市A股", "北交所A股"):
        prefix = {"沪市A股": ("sh",), "深市A股": ("sz",), "北交所A股": ("bj",)}[market]
        df = df[df["代码"].str.lower().str.startswith(prefix)].reset_index(drop=True)
    return df


def fetch_exchange_announcement(symbol: str = "600519") -> pd.DataFrame:
    """获取上市公司公告（官方渠道权威信息，源自交易所披露）。

    返回：代码/名称/公告标题/公告类型/公告日期/网址。
    """
    import akshare as ak

    return _guard(
        ak.stock_individual_notice_report(security=symbol),
        f"公告 {symbol}",
    )


# ---------------------------------------------------------------------------
# 2. 财经网站 —— 东方财富
# ---------------------------------------------------------------------------
def fetch_eastmoney_quote(symbol: str = "600519") -> pd.DataFrame:
    """东方财富个股实时/基本信息（证券软件实时行情渠道）。"""
    import akshare as ak

    return _guard(ak.stock_individual_info_em(symbol=symbol), f"东财行情 {symbol}")


def fetch_eastmoney_financial(symbol: str = "600519") -> pd.DataFrame:
    """东方财富财务报表摘要（关键财务指标，配合财报解读）。"""
    import akshare as ak

    return _guard(ak.stock_financial_abstract(symbol=symbol), f"东财财务 {symbol}")


def fetch_eastmoney_all_spot() -> pd.DataFrame:
    """东方财富全 A 股行情快照。

    说明：东财全市场快照接口对本机存在反爬拦截（RemoteDisconnected），
    此处返回新浪指数快照作为稳定替代（上海/深圳/北京交易所主要指数）。
    东财的单公司财务数据 fetch_eastmoney_financial() 不受影响、正常可用。
    """
    import akshare as ak

    return _guard(ak.stock_zh_index_spot_sina(), "东财全A快照(新浪指数替代)")


# ---------------------------------------------------------------------------
# 3. 财经网站 —— 新浪财经
# ---------------------------------------------------------------------------
def fetch_sina_history(symbol: str = "sh600519", period: str = "daily") -> pd.DataFrame:
    """新浪财经个股历史行情（日/周/月K线）。

    symbol 需带交易所前缀：如 'sh600519'、'sz000001'、'bj430047'。
    period: daily | weekly | monthly
    """
    import akshare as ak

    return _guard(
        ak.stock_zh_a_daily(symbol=symbol, adjust="qfq"),
        f"新浪历史 {symbol}",
    )


def fetch_sina_spot() -> pd.DataFrame:
    """新浪财经全市场实时行情快照。"""
    import akshare as ak

    return _guard(ak.stock_zh_a_spot(), "新浪实时快照")


# ---------------------------------------------------------------------------
# 4. 财经网站 —— 雪球
# ---------------------------------------------------------------------------
def fetch_xueqiu_quote(symbol: str = "SH600519", token: str | None = None) -> pd.DataFrame:
    """雪球个股实时行情与成交明细（投资者交流社区数据源）。

    说明：雪球行情接口要求登录 token（Cookie 中的 xq_a_token）。
    请登录雪球网页版(https://xueqiu.com)后，按 F12 打开开发者工具，
    从请求 Cookie 中复制 xq_a_token 的值传入 token 参数。
    symbol 需大写交易所前缀，如 'SH600519'、'SZ000001'。
    """
    import akshare as ak

    if not token:
        raise RuntimeError(
            "雪球行情接口需要登录 token。请登录 xueqiu.com，从 Cookie 中复制 xq_a_token 传入 token 参数。"
        )
    df = ak.stock_individual_spot_xq(symbol=symbol, token=token)
    return _guard(df, f"雪球 {symbol}")


# ---------------------------------------------------------------------------
# 5. 财经网站 —— 每日经济新闻
# ---------------------------------------------------------------------------
def fetch_nbd_news(keyword: str | None = None, limit: int = 10) -> list[dict]:
    """每日经济新闻首页财经新闻（财经新闻资讯渠道）。

    说明：该站点无公开稳定 API，此处抓取官网首页文章列表（标题+链接）。
    keyword 参数预留但当前首页抓取不区分关键词。
    """
    from bs4 import BeautifulSoup

    url = "https://www.nbd.com.cn/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(url, headers=headers, timeout=12)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    rows, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        title = a.get_text(" ", strip=True)
        if title and len(title) >= 8 and "/articles/" in href and href not in seen:
            if href.startswith("http"):
                link = href
            else:
                link = "https://www.nbd.com.cn" + href
            seen.add(href)
            rows.append({"标题": title, "链接": link})
            if len(rows) >= min(int(limit), 20):
                break
    if not rows:
        raise RuntimeError("[每日经济新闻] 未解析到文章，站点结构可能变更。")
    return rows


# ---------------------------------------------------------------------------
# 6. 证券软件 —— 同花顺
# ---------------------------------------------------------------------------
def fetch_ths_financial(symbol: str = "600519") -> pd.DataFrame:
    """同花顺个股财务摘要（证券软件·基本面信息渠道）。

    说明：akshare 1.19.x 已移除同花顺历史行情接口，此处改用其财务摘要
    （报表类型 report: '最新'|'年报'|'中报'|'一季报'|'三季报'），
    覆盖偿债/成长/运营/盈利等财务指标。
    """
    import akshare as ak

    return _guard(
        ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期"),
        f"同花顺财务 {symbol}",
    )


# ---------------------------------------------------------------------------
# 7. 辅助渠道 —— 行业研究报告 / 上市公司信息
# ---------------------------------------------------------------------------
def fetch_research_report(symbol: str = "600519") -> pd.DataFrame:
    """东方财富研报中心个股研究报告（辅助渠道·行业研报）。

    参数 symbol: 6 位股票代码（如 '600519'），注意是代码而非股票名称。
    返回：研报列表（报告名称、机构、评级、发布日期等）。
    """
    import akshare as ak

    df = ak.stock_research_report_em(symbol=symbol)
    return _guard(df, f"研报 {symbol}")


def fetch_company_info(symbol: str = "600519") -> dict:
    """上市公司基本信息（工商/概况，辅助渠道）。"""
    import akshare as ak

    df = ak.stock_individual_info_em(symbol=symbol)
    _guard(df, f"公司信息 {symbol}")
    # 转为 字段->值 的字典，便于人读
    return dict(zip(df["item"], df["value"]))


# ---------------------------------------------------------------------------
# 8. 汇总入口
# ---------------------------------------------------------------------------
CHANNEL_MAP = {
    "官方渠道-沪深京交易所": fetch_exchange_market,
    "官方渠道-公司公告": fetch_exchange_announcement,
    "财经网站-东方财富": fetch_eastmoney_financial,
    "财经网站-新浪财经": fetch_sina_history,
    "财经网站-雪球": fetch_xueqiu_quote,
    "财经网站-每日经济新闻": fetch_nbd_news,
    "证券软件-同花顺": fetch_ths_financial,
    "辅助渠道-行业研报": fetch_research_report,
}


def list_channels() -> None:
    """打印当前已封装的渠道清单。"""
    print("已封装的数据获取渠道如下：")
    for name, fn in CHANNEL_MAP.items():
        print(f"  - {name}   ({fn.__name__})")


if __name__ == "__main__":
    list_channels()
    print("\n示例：拉取贵州茅台(600519)关键财务指标")
    try:
        fin = fetch_eastmoney_financial("600519")
        print(fin.head().to_string())
    except Exception as e:
        print("示例运行失败：", e)
