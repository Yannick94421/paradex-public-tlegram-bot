from typing import List
import aiohttp
from typing import Optional,Dict,Any,Tuple
import time

PARADEX_API_URL = "https://api.prod.paradex.trade/v1"

def flatten_signature(sig: List[int]) -> str:
    return f'["{sig[0]}","{sig[1]}"]'

def good_time(timesx : int):
    t = time.localtime(timesx/1000)
    return time.strftime("%Hh%M", t)

async def make_request(
    method: str,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Tuple[aiohttp.ClientResponse, bool]:
    url = f"{PARADEX_API_URL}{path}"
    

    async with aiohttp.ClientSession() as session:
        async with session.request(
            method, url, headers=headers, json=data
        ) as response:
            status_code = response.status

            try:
                response_data = await response.json()
            except aiohttp.ContentTypeError:
                response_data = {}

            if not (200 <= status_code < 300):
                return response, False

            return response, True

def is_token_expired(status_code: int, response: dict) -> bool:
    return (
        True
        if (
            status_code == 401
            and response["message"].startswith(
                "invalid bearer jwt: token is expired by"
            )
        )
        else False
    )
