"""Market data API endpoints."""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.api.auth import get_current_user
from tastytrade_mcp.api.helpers import get_active_broker_link
from tastytrade_mcp.db.session import get_session
from tastytrade_mcp.models.auth import BrokerLink, LinkStatus
from tastytrade_mcp.models.user import User
from tastytrade_mcp.services.cache import get_cache
from tastytrade_mcp.services.tastytrade import TastyTradeService
from tastytrade_mcp.utils.logging import get_logger
from decimal import Decimal
from enum import Enum

router = APIRouter(prefix="/market-data", tags=["Market Data"])
logger = get_logger(__name__)

# Rate limiting
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 60  # seconds
QUOTE_CACHE_TTL = 5  # seconds for quotes
BATCH_QUOTE_LIMIT = 50  # max symbols per batch
HISTORICAL_CACHE_TTL_INTRADAY = 3600  # 1 hour for intraday data
HISTORICAL_CACHE_TTL_DAILY = 86400  # 24 hours for daily+ data
MAX_DAILY_DATA_POINTS = 10000  # Max data points per day per user


class Timeframe(str, Enum):
    """Supported timeframes for historical data."""
    MIN_1 = "1min"
    MIN_5 = "5min"
    MIN_15 = "15min"
    MIN_30 = "30min"
    HOUR_1 = "1hour"
    DAY_1 = "1day"
    WEEK_1 = "1week"
    MONTH_1 = "1month"


# Response Models
class SymbolDetails(BaseModel):
    """Symbol search result details."""
    symbol: str = Field(..., description="Trading symbol")
    name: str = Field(..., description="Company/instrument name")
    asset_type: str = Field(..., description="Asset type (equity, etf, option, future)")
    exchange: Optional[str] = Field(None, description="Primary exchange")
    tradable: bool = Field(True, description="Whether instrument is tradable")
    market_hours: Optional[str] = Field(None, description="Trading hours")
    description: Optional[str] = Field(None, description="Instrument description")
    sector: Optional[str] = Field(None, description="Sector classification")
    active: bool = Field(True, description="Whether instrument is active")
    has_options: bool = Field(False, description="Whether options are available")
    relevance_score: float = Field(0.0, description="Search relevance score")


class SymbolSearchResponse(BaseModel):
    """Response for symbol search endpoint."""
    query: str = Field(..., description="Original search query")
    symbols: List[SymbolDetails] = Field(..., description="Matching symbols")
    total_results: int = Field(..., description="Total number of results")
    cached: bool = Field(False, description="Whether results were cached")
    query_time_ms: int = Field(..., description="Query execution time")
    suggestions: List[str] = Field(default_factory=list, description="Alternative search suggestions")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QuoteData(BaseModel):
    """Real-time quote data for a symbol."""
    symbol: str = Field(..., description="Trading symbol")
    bid: Optional[Decimal] = Field(None, description="Bid price")
    ask: Optional[Decimal] = Field(None, description="Ask price")
    last: Decimal = Field(..., description="Last traded price")
    volume: int = Field(..., description="Daily volume")
    market_session: str = Field(..., description="Market session (pre-market, regular, after-hours)")
    change: Decimal = Field(..., description="Price change from previous close")
    change_percent: Decimal = Field(..., description="Percentage change")
    day_high: Decimal = Field(..., description="Daily high price")
    day_low: Decimal = Field(..., description="Daily low price")
    prev_close: Decimal = Field(..., description="Previous close price")
    open: Optional[Decimal] = Field(None, description="Opening price")
    timestamp: datetime = Field(..., description="Quote timestamp")

    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: lambda v: float(v) if v else None,
            datetime: lambda v: v.isoformat() if v else None
        }


class QuoteResponse(BaseModel):
    """Response for quote endpoint."""
    quotes: List[QuoteData] = Field(..., description="Quote data for requested symbols")
    request_time_ms: int = Field(..., description="Request processing time")
    cached: bool = Field(False, description="Whether quotes were cached")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BatchQuoteRequest(BaseModel):
    """Request for batch quote retrieval."""
    symbols: List[str] = Field(..., min_items=1, max_items=50, description="List of symbols")
    include_extended: bool = Field(False, description="Include extended hours quotes")


class OHLCVData(BaseModel):
    """OHLCV data point for historical data."""
    timestamp: datetime = Field(..., description="Period timestamp")
    open: Decimal = Field(..., description="Opening price")
    high: Decimal = Field(..., description="High price")
    low: Decimal = Field(..., description="Low price")
    close: Decimal = Field(..., description="Closing price")
    volume: int = Field(..., description="Trading volume")

    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: lambda v: float(v) if v else None,
            datetime: lambda v: v.isoformat() if v else None
        }


class HistoricalMetadata(BaseModel):
    """Metadata for historical data response."""
    total_periods: int = Field(..., description="Total number of periods returned")
    missing_periods: int = Field(0, description="Number of missing data periods")
    data_source: str = Field("tastyworks", description="Data source")
    completeness: float = Field(..., description="Data completeness percentage")
    timezone: str = Field("America/New_York", description="Data timezone")


class HistoricalDataRequest(BaseModel):
    """Request for historical data."""
    symbol: str = Field(..., description="Trading symbol")
    timeframe: Timeframe = Field(..., description="Data timeframe")
    start_date: datetime = Field(..., description="Start date (inclusive)")
    end_date: datetime = Field(..., description="End date (inclusive)")
    include_extended_hours: bool = Field(False, description="Include extended hours data")


class HistoricalDataResponse(BaseModel):
    """Response for historical data endpoint."""
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Data timeframe")
    data: List[OHLCVData] = Field(..., description="OHLCV data points")
    metadata: HistoricalMetadata = Field(..., description="Response metadata")
    cached: bool = Field(False, description="Whether data was cached")
    request_time_ms: int = Field(..., description="Request processing time")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


@router.get("/search", response_model=SymbolSearchResponse)
async def search_symbols(
    query: str = Query(..., min_length=1, max_length=50, description="Search query"),
    asset_type: Optional[str] = Query(None, description="Filter by asset type"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SymbolSearchResponse:
    """
    Search for trading symbols across all asset types.

    Supports partial matches, fuzzy search, and common abbreviations.
    Results are ranked by relevance and trading volume.
    """
    start_time = datetime.utcnow()

    # Check rate limiting
    await _check_rate_limit(current_user.id)

    # Check cache first
    cache = await get_cache()
    cache_key = f"symbol_search:{query.upper()}:{asset_type or 'all'}:{limit}"

    if cache:
        cached_data = await cache.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached symbol search for query '{query}'")
            cached_data["cached"] = True
            cached_data["query_time_ms"] = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return SymbolSearchResponse(**cached_data)

    # Get broker link
    broker_link = await get_active_broker_link(session, current_user)

    if not broker_link or broker_link.status != LinkStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active TastyTrade account linked. Please complete OAuth flow first."
        )

    try:
        # Initialize TastyTrade service
        tastytrade = TastyTradeService(session)

        # Search symbols
        results = await tastytrade.search_symbols(broker_link, query, limit)

        # Process and enrich results
        symbols = []
        for idx, result in enumerate(results):
            symbol_detail = _process_symbol_result(result, query, idx)

            # Apply asset type filter if specified
            if asset_type and symbol_detail.asset_type.lower() != asset_type.lower():
                continue

            symbols.append(symbol_detail)

        # Sort by relevance score
        symbols.sort(key=lambda x: x.relevance_score, reverse=True)

        # Limit results
        symbols = symbols[:limit]

        # Generate suggestions if no results
        suggestions = []
        if not symbols:
            suggestions = _generate_search_suggestions(query)

        # Calculate query time
        query_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        response_data = {
            "query": query,
            "symbols": symbols,
            "total_results": len(symbols),
            "cached": False,
            "query_time_ms": query_time_ms,
            "suggestions": suggestions,
            "timestamp": datetime.utcnow()
        }

        # Cache results for 24 hours
        if cache and symbols:
            await cache.set(cache_key, response_data, ttl=86400)  # 24 hours
            logger.info(f"Cached {len(symbols)} symbol results for query '{query}'")

        return SymbolSearchResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search symbols: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to search symbols. Please try again later."
        )


def _process_symbol_result(result: dict, query: str, index: int) -> SymbolDetails:
    """Process raw symbol result into SymbolDetails model."""
    symbol = result.get("symbol", "")
    name = result.get("description", result.get("name", ""))

    # Determine asset type
    asset_type = result.get("instrument-type", "UNKNOWN")
    if asset_type == "EQUITY":
        asset_type = "equity"
    elif asset_type == "ETF":
        asset_type = "etf"
    elif asset_type == "EQUITY_OPTION":
        asset_type = "option"
    elif asset_type == "FUTURE":
        asset_type = "future"
    else:
        asset_type = asset_type.lower()

    # Calculate relevance score
    relevance_score = _calculate_relevance_score(symbol, name, query, index)

    # Parse market hours
    market_hours = _parse_market_hours(result)

    return SymbolDetails(
        symbol=symbol,
        name=name,
        asset_type=asset_type,
        exchange=result.get("exchange"),
        tradable=not result.get("is-closed", False),
        market_hours=market_hours,
        description=result.get("description"),
        sector=result.get("sector"),
        active=result.get("active", True),
        has_options=result.get("has-options", False),
        relevance_score=relevance_score
    )


def _calculate_relevance_score(symbol: str, name: str, query: str, index: int) -> float:
    """Calculate relevance score for search results."""
    query_upper = query.upper()
    symbol_upper = symbol.upper()
    name_upper = name.upper() if name else ""

    score = 100.0

    # Exact symbol match gets highest score
    if symbol_upper == query_upper:
        score += 100.0
    # Symbol starts with query
    elif symbol_upper.startswith(query_upper):
        score += 75.0
    # Symbol contains query
    elif query_upper in symbol_upper:
        score += 50.0

    # Name matches
    if query_upper in name_upper:
        score += 25.0

    # Penalize based on position in results
    score -= index * 2.0

    return max(score, 0.0)


def _parse_market_hours(result: dict) -> Optional[str]:
    """Parse market hours from result."""
    # This would need actual market hours data from API
    # For now, return standard hours for equities
    if result.get("instrument-type") in ["EQUITY", "ETF"]:
        return "09:30-16:00 ET"
    elif result.get("instrument-type") == "FUTURE":
        return "Various (check contract specs)"
    else:
        return None


def _generate_search_suggestions(query: str) -> List[str]:
    """Generate alternative search suggestions."""
    suggestions = []

    # Suggest without special characters
    clean_query = ''.join(c for c in query if c.isalnum() or c.isspace())
    if clean_query != query:
        suggestions.append(clean_query)

    # Suggest common alternatives
    if len(query) <= 5:
        suggestions.append(f"Try searching by company name instead of symbol")
    else:
        suggestions.append(f"Try searching by symbol instead of company name")

    # Suggest checking spelling
    if not suggestions:
        suggestions.append("Check spelling or try a different search term")

    return suggestions[:3]  # Limit to 3 suggestions


async def _check_rate_limit(user_id: UUID):
    """Check and enforce rate limiting."""
    cache = await get_cache()
    if not cache:
        return  # Skip rate limiting if no cache

    rate_key = f"rate_limit:search:{user_id}"
    current_count = await cache.get(rate_key)

    if current_count is None:
        # First request in window
        await cache.set(rate_key, 1, ttl=RATE_LIMIT_WINDOW)
    elif int(current_count) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds."
        )
    else:
        # Increment counter
        new_count = int(current_count) + 1
        await cache.set(rate_key, new_count, ttl=RATE_LIMIT_WINDOW)


@router.get("/symbols/{symbol}")
async def get_symbol_details(
    symbol: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Get detailed information for a specific symbol.

    Returns comprehensive instrument data including specifications and trading details.
    """
    # Search for exact symbol match
    search_response = await search_symbols(
        query=symbol,
        asset_type=None,
        limit=1,
        current_user=current_user,
        session=session
    )

    if not search_response.symbols:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{symbol}' not found"
        )

    symbol_data = search_response.symbols[0]

    # Get broker link for additional data
    broker_link = await get_active_broker_link(session, current_user)

    # Could fetch additional details here like:
    # - Option chain availability
    # - Trading specifications
    # - Historical volatility
    # - Recent news/events

    return {
        "symbol": symbol_data.symbol,
        "name": symbol_data.name,
        "asset_type": symbol_data.asset_type,
        "exchange": symbol_data.exchange,
        "tradable": symbol_data.tradable,
        "market_hours": symbol_data.market_hours,
        "description": symbol_data.description,
        "sector": symbol_data.sector,
        "active": symbol_data.active,
        "has_options": symbol_data.has_options,
        "specifications": {
            "tick_size": 0.01,  # Would come from API
            "lot_size": 1,  # Would come from API
            "margin_requirement": "25%"  # Would come from API
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/quote/{symbol}", response_model=QuoteResponse)
async def get_quote(
    symbol: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> QuoteResponse:
    """
    Get real-time quote for a single symbol.

    Returns current bid/ask, last price, volume, and price changes.
    Quotes are cached for 5 seconds.
    """
    # Use batch endpoint internally for consistency
    batch_request = BatchQuoteRequest(symbols=[symbol.upper()])
    return await get_batch_quotes(batch_request, current_user, session)


@router.post("/quotes", response_model=QuoteResponse)
async def get_batch_quotes(
    request: BatchQuoteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> QuoteResponse:
    """
    Get real-time quotes for multiple symbols.

    Supports up to 50 symbols per request.
    Quotes are cached for 5 seconds.
    """
    start_time = datetime.utcnow()

    # Check rate limiting
    await _check_rate_limit(current_user.id)

    # Normalize symbols
    symbols = [s.upper() for s in request.symbols]

    # Check cache
    cache = await get_cache()
    cached_quotes = []
    uncached_symbols = []

    if cache:
        for symbol in symbols:
            cache_key = f"quote:{symbol}"
            cached_data = await cache.get(cache_key)
            if cached_data:
                cached_quotes.append(cached_data)
            else:
                uncached_symbols.append(symbol)
    else:
        uncached_symbols = symbols

    # If all quotes are cached, return them
    if not uncached_symbols and cached_quotes:
        query_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        return QuoteResponse(
            quotes=cached_quotes,
            request_time_ms=query_time_ms,
            cached=True,
            timestamp=datetime.utcnow()
        )

    # Get broker link
    broker_link = await get_active_broker_link(session, current_user)

    if not broker_link or broker_link.status != LinkStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active TastyTrade account linked."
        )

    try:
        # Initialize TastyTrade service
        tastytrade = TastyTradeService(session)

        # Fetch quotes for uncached symbols
        fresh_quotes = []
        if uncached_symbols:
            market_data = await tastytrade.get_market_data(broker_link, uncached_symbols)

            for symbol in uncached_symbols:
                quote_data = market_data.get(symbol, {})
                if quote_data:
                    quote = _process_quote_data(symbol, quote_data)
                    fresh_quotes.append(quote)

                    # Cache the quote
                    if cache:
                        await cache.set(f"quote:{symbol}", quote.dict(), ttl=QUOTE_CACHE_TTL)

        # Combine cached and fresh quotes
        all_quotes = cached_quotes + fresh_quotes

        # Sort quotes to match request order
        symbol_order = {s: i for i, s in enumerate(symbols)}
        all_quotes.sort(key=lambda q: symbol_order.get(q.symbol if isinstance(q, QuoteData) else q.get("symbol"), 999))

        # Convert cached dicts to QuoteData objects
        final_quotes = []
        for q in all_quotes:
            if isinstance(q, dict):
                final_quotes.append(QuoteData(**q))
            else:
                final_quotes.append(q)

        query_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        return QuoteResponse(
            quotes=final_quotes,
            request_time_ms=query_time_ms,
            cached=len(cached_quotes) > 0,
            timestamp=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch quotes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to fetch quote data. Please try again later."
        )


def _process_quote_data(symbol: str, data: dict) -> QuoteData:
    """Process raw quote data into QuoteData model."""
    # Parse decimals safely
    bid = Decimal(str(data.get("bid", 0))) if data.get("bid") else None
    ask = Decimal(str(data.get("ask", 0))) if data.get("ask") else None
    last = Decimal(str(data.get("last", data.get("mark", 0))))

    prev_close = Decimal(str(data.get("previous-close", last)))
    change = last - prev_close
    change_percent = (change / prev_close * 100) if prev_close and prev_close != 0 else Decimal(0)

    # Determine market session
    market_session = _determine_quote_session()

    return QuoteData(
        symbol=symbol,
        bid=bid,
        ask=ask,
        last=last,
        volume=int(data.get("volume", 0)),
        market_session=market_session,
        change=change,
        change_percent=change_percent,
        day_high=Decimal(str(data.get("high", last))),
        day_low=Decimal(str(data.get("low", last))),
        prev_close=prev_close,
        open=Decimal(str(data.get("open", 0))) if data.get("open") else None,
        timestamp=datetime.utcnow()
    )


def _determine_quote_session() -> str:
    """Determine current market session for quotes."""
    from datetime import time
    import pytz

    # Get current time in ET
    et_tz = pytz.timezone('US/Eastern')
    now_et = datetime.now(et_tz)
    current_time = now_et.time()
    weekday = now_et.weekday()

    # Market closed on weekends
    if weekday >= 5:  # Saturday = 5, Sunday = 6
        return "closed"

    # Define market hours (ET)
    pre_market_start = time(4, 0)
    regular_start = time(9, 30)
    regular_end = time(16, 0)
    after_hours_end = time(20, 0)

    if current_time < pre_market_start:
        return "closed"
    elif current_time < regular_start:
        return "pre-market"
    elif current_time < regular_end:
        return "regular"
    elif current_time < after_hours_end:
        return "after-hours"
    else:
        return "closed"


@router.post("/historical", response_model=HistoricalDataResponse)
async def get_historical_data(
    request: HistoricalDataRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> HistoricalDataResponse:
    """
    Retrieve historical OHLCV data for a symbol.

    Supports multiple timeframes from 1-minute to monthly.
    Data is cached based on timeframe (1 hour for intraday, 24 hours for daily+).
    Maximum date ranges enforced to prevent excessive data requests.
    """
    start_time = datetime.utcnow()

    # Validate date range
    _validate_date_range(request.timeframe, request.start_date, request.end_date)

    # Check daily data point limit
    await _check_data_point_limit(current_user.id, request)

    # Check cache
    cache = await get_cache()
    cache_key = (
        f"historical:{request.symbol}:{request.timeframe}:"
        f"{request.start_date.date()}:{request.end_date.date()}:"
        f"{request.include_extended_hours}"
    )

    if cache:
        cached_data = await cache.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached historical data for {request.symbol}")
            cached_data["cached"] = True
            cached_data["request_time_ms"] = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return HistoricalDataResponse(**cached_data)

    # Get broker link
    broker_link = await get_active_broker_link(session, current_user)

    if not broker_link or broker_link.status != LinkStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active TastyTrade account linked."
        )

    try:
        # Initialize TastyTrade service
        tastytrade = TastyTradeService(session)

        # Fetch historical data
        raw_data = await tastytrade.get_historical_data(
            broker_link,
            request.symbol,
            request.timeframe.value,
            request.start_date,
            request.end_date,
            request.include_extended_hours
        )

        # Process data points
        ohlcv_data = []
        for point in raw_data:
            ohlcv = OHLCVData(
                timestamp=point.get("time"),
                open=Decimal(str(point.get("open", 0))),
                high=Decimal(str(point.get("high", 0))),
                low=Decimal(str(point.get("low", 0))),
                close=Decimal(str(point.get("close", 0))),
                volume=int(point.get("volume", 0))
            )
            ohlcv_data.append(ohlcv)

        # Sort by timestamp
        ohlcv_data.sort(key=lambda x: x.timestamp)

        # Calculate metadata
        total_periods = len(ohlcv_data)
        expected_periods = _calculate_expected_periods(
            request.timeframe,
            request.start_date,
            request.end_date
        )
        missing_periods = max(0, expected_periods - total_periods)
        completeness = (total_periods / expected_periods * 100) if expected_periods > 0 else 0

        metadata = HistoricalMetadata(
            total_periods=total_periods,
            missing_periods=missing_periods,
            data_source="tastyworks",
            completeness=completeness,
            timezone="America/New_York"
        )

        # Calculate request time
        request_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        response_data = {
            "symbol": request.symbol.upper(),
            "timeframe": request.timeframe.value,
            "data": ohlcv_data,
            "metadata": metadata,
            "cached": False,
            "request_time_ms": request_time_ms,
            "timestamp": datetime.utcnow()
        }

        # Cache the response
        if cache and ohlcv_data:
            # Determine cache TTL based on timeframe
            if request.timeframe in [Timeframe.MIN_1, Timeframe.MIN_5, Timeframe.MIN_15,
                                    Timeframe.MIN_30, Timeframe.HOUR_1]:
                ttl = HISTORICAL_CACHE_TTL_INTRADAY
            else:
                ttl = HISTORICAL_CACHE_TTL_DAILY

            await cache.set(cache_key, response_data, ttl=ttl)
            logger.info(f"Cached {total_periods} historical data points for {request.symbol}")

        return HistoricalDataResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch historical data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to fetch historical data. Please try again later."
        )


def _validate_date_range(timeframe: Timeframe, start_date: datetime, end_date: datetime):
    """Validate date range for historical data request."""
    if start_date >= end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before end date"
        )

    # Calculate date difference
    date_diff = end_date - start_date

    # Enforce maximum ranges based on timeframe
    if timeframe == Timeframe.MIN_1:
        max_days = 30
    elif timeframe in [Timeframe.MIN_5, Timeframe.MIN_15]:
        max_days = 90
    elif timeframe in [Timeframe.MIN_30, Timeframe.HOUR_1]:
        max_days = 180
    elif timeframe == Timeframe.DAY_1:
        max_days = 730  # 2 years
    else:  # WEEK_1, MONTH_1
        max_days = 1825  # 5 years

    if date_diff.days > max_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum range for {timeframe.value} data is {max_days} days"
        )


async def _check_data_point_limit(user_id: UUID, request: HistoricalDataRequest):
    """Check if user has exceeded daily data point limit."""
    cache = await get_cache()
    if not cache:
        return

    # Track daily data point usage
    today = datetime.utcnow().date()
    usage_key = f"data_points:{user_id}:{today}"

    # Estimate data points for this request
    estimated_points = _calculate_expected_periods(
        request.timeframe,
        request.start_date,
        request.end_date
    )

    current_usage = await cache.get(usage_key)
    current_usage = int(current_usage) if current_usage else 0

    if current_usage + estimated_points > MAX_DAILY_DATA_POINTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily data point limit exceeded ({MAX_DAILY_DATA_POINTS} points)"
        )

    # Update usage counter
    new_usage = current_usage + estimated_points
    await cache.set(usage_key, new_usage, ttl=86400)  # 24 hours


def _calculate_expected_periods(timeframe: Timeframe, start_date: datetime, end_date: datetime) -> int:
    """Calculate expected number of data periods for given timeframe and date range."""
    import pytz
    from datetime import time

    # Get timezone
    et_tz = pytz.timezone('US/Eastern')

    # Calculate business days between dates
    total_days = (end_date.date() - start_date.date()).days + 1

    # Estimate based on timeframe (simplified - doesn't account for holidays)
    if timeframe == Timeframe.MIN_1:
        # 390 minutes per trading day (9:30-16:00)
        return total_days * 390
    elif timeframe == Timeframe.MIN_5:
        return total_days * 78
    elif timeframe == Timeframe.MIN_15:
        return total_days * 26
    elif timeframe == Timeframe.MIN_30:
        return total_days * 13
    elif timeframe == Timeframe.HOUR_1:
        return total_days * 7
    elif timeframe == Timeframe.DAY_1:
        # Roughly 252 trading days per year
        return int(total_days * 0.7)  # Approximate for weekdays
    elif timeframe == Timeframe.WEEK_1:
        return total_days // 7
    elif timeframe == Timeframe.MONTH_1:
        return total_days // 30

    return total_days


@router.get("/historical/{symbol}")
async def get_historical_data_simple(
    symbol: str,
    timeframe: Timeframe = Query(Timeframe.DAY_1, description="Data timeframe"),
    days: int = Query(30, ge=1, le=730, description="Number of days of data"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> HistoricalDataResponse:
    """
    Simplified endpoint to get historical data for the last N days.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    request = HistoricalDataRequest(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        include_extended_hours=False
    )

    return await get_historical_data(request, current_user, session)


@router.get("/exchanges")
async def list_exchanges(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    List available exchanges and their trading hours.
    """
    return {
        "exchanges": [
            {
                "code": "NASDAQ",
                "name": "NASDAQ Stock Market",
                "hours": "09:30-16:00 ET",
                "timezone": "America/New_York",
                "asset_types": ["equity", "etf"]
            },
            {
                "code": "NYSE",
                "name": "New York Stock Exchange",
                "hours": "09:30-16:00 ET",
                "timezone": "America/New_York",
                "asset_types": ["equity", "etf"]
            },
            {
                "code": "CBOE",
                "name": "Chicago Board Options Exchange",
                "hours": "09:30-16:15 ET",
                "timezone": "America/New_York",
                "asset_types": ["option"]
            },
            {
                "code": "CME",
                "name": "Chicago Mercantile Exchange",
                "hours": "Various by product",
                "timezone": "America/Chicago",
                "asset_types": ["future"]
            }
        ],
        "timestamp": datetime.utcnow().isoformat()
    }