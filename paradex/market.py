from paradex.utils import make_request,Dict,Optional,Any,Tuple,good_time
from paradex.types import OrderBook,MarketOptionInfoPrice,Decimal,Trade
import time
import asyncio
async def get_market_pair(market: str) -> dict:
    
    path = f"/markets?market={market}"
    method = "GET"
    headers = {
        'Accept': 'application/json'
        }
    response, success = await make_request(method, path, headers=headers)
    if not success:
        return None
    data = await response.json()
    # Selon la structure de l'API, les résultats sont dans data['results']
    results = data.get('results', [])
    if not results:
        return None
    return results[0]

async def get_bbo(market: str) -> dict:
    path = f"/bbo/{market}"
    method = "GET"
    headers = {
        'Accept': 'application/json'
    }
    response, success = await make_request(method, path, headers=headers)
    if not success:
        return None
    datf = await response.json()
    data = MarketOptionInfoPrice(
        market=datf.get('market'),
        ask=(datf['ask']) if datf.get('ask') is not None else None,
        bid=(datf['bid']) if datf.get('bid') is not None else None,
        askSize=(datf['ask_size']) if datf.get('ask_size') is not None else None,
        bidSize=(datf['bid_size']) if datf.get('bid_size') is not None else None
    )

    return data.to_dict()

async def get_orderbook(market: str, depth: int = 5) -> dict:
    path = f"/orderbook/{market}"
    method = "GET"
    headers = {
        'Accept': 'application/json'
    }
    response, success = await make_request(method, path, headers=headers)
    if not success:
        return None
    datf = await response.json()
    # On limite la profondeur à 'depth' pour bids et asks
    orderbook = {
        'market': datf.get('market'),
        'bids': datf.get('bids', [])[:depth],
        'asks': datf.get('asks', [])[:depth]
    }
    return orderbook

async def get_trades(market: str, limit: int = 10) -> dict:
    
    path = f"/trades?market={market}&limit={limit}"
    method = "GET"
    headers = {
        'Accept': 'application/json'
    }
    response, success = await make_request(method, path, headers=headers)
    if not success:
        return None
    data = await response.json()
    # Les résultats sont généralement dans data['results']
    data = data.get('results', [])[:limit]
    list_trades = []
    for trade in data:
        t = Trade(
            price=str(trade['price']),
            size=str(trade['size']),
            side=str(trade['side']),
            time=str(good_time(int(trade.get('created_at'))))
        )
        list_trades.append(t)
    return list_trades


if __name__ == "__main__":
    async def main():
        market = "BTC-USD-140000-C"
        market2 = "BTC-USD-85000-P"
        """market_info = await get_market_pair(market)
        if market_info:
            print(f"Market Info for {market}: {market_info}")
        else:
            print(f"Market {market} not found.")"""
    
        bbo_info = await get_bbo(market2)
        if bbo_info:
            print(f"BBO Info for {market2}: {bbo_info}")
        else:
            print(f"BBO for {market2} not found.")
        
        
    
    asyncio.run(main())