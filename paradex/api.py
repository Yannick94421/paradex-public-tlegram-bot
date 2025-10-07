import time
from typing import Any, Dict, Optional, Tuple
import asyncio
from decimal import Decimal
from paradex.types import Order, OrderSide, OrderType, Position,OrderPlaced

import aiohttp
from loguru import logger
from starknet_py.common import int_from_bytes

from paradex.exceptions import ParadexAPIError,OrderCancelError
from paradex.types import Order

from .account import get_account
from .messages import (
    build_auth_message,
    build_onboarding_message,
    build_order_sign_message,
)
from .utils import flatten_signature, is_token_expired


class ParadexAPI:
    BASE_URL = "https://api.prod.paradex.trade/v1"

    def __init__(
        self,
        account_address: Optional[str] = None,
        private_key: Optional[str] = None,
        jwt_token: Optional[str] = None,
    ):
        self.jwt_token = jwt_token
        self.account_address = account_address
        self.private_key = private_key
        self.last_refresh = 0
        self.config: Dict[str, Any] = {}

    async def _create_headers(self) -> Dict[str, str]:
        if not self.jwt_token:
            return {}
        return {"Authorization": f"Bearer {self.jwt_token}"}

    async def _make_request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        check_jwt: bool = True,
    ) -> Tuple[aiohttp.ClientResponse, bool]:
        url = f"{self.BASE_URL}{path}"
        if headers is None:
            headers = await self._create_headers()

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, headers=headers, json=data
            ) as response:
                status_code = response.status

                try:
                    response_data = await response.json()
                except aiohttp.ContentTypeError:
                    response_data = {}

                if check_jwt:
                    await self._check_token_expiry(status_code, response_data)

                if not (200 <= status_code < 300):
                    return response, False

                return response, True

    async def get_config(self) -> Dict[str, Any]:
        method = "GET"
        path = "/system/config"
        response, success = await self._make_request(method, path, check_jwt=False)

        response_status = response.status
        response_data = await response.json()

        if success:
            self.config = await response.json()
            return response_data

        logger.error(f"Unable to [{method}] {path}")
        logger.error(f"Status Code: {response_status}")
        logger.error(f"Response Text: {response_data}")
        raise ParadexAPIError("Failed to get Paradex API configuration")

    async def get_jwt_token(self) -> str:
        if not self.config:
            await self.get_config()

        
        chain = int_from_bytes(self.config["starknet_chain_id"].encode())
        account = get_account(
            account_address=self.account_address,
            account_key=self.private_key,
            paradex_config=self.config,
        )

        now = int(time.time())
        expiry = now + 24 * 60 * 60
        message = build_auth_message(chain, now, expiry)
        sig = account.sign_message(message)

        method = "POST"
        path = "/auth"

        headers = {
            "PARADEX-STARKNET-ACCOUNT": self.account_address,
            "PARADEX-STARKNET-SIGNATURE": flatten_signature(sig),
            "PARADEX-TIMESTAMP": str(now),
            "PARADEX-SIGNATURE-EXPIRATION": str(expiry),
        }

        response, success = await self._make_request(
            method, path, headers=headers, check_jwt=False
        )

        response_status = response.status
        response_data = await response.json()

        if success:
            self.jwt_token = response_data.get("jwt_token", "")
            return self.jwt_token

        logger.error(f"Unable to [{method}] {path}")
        logger.error(f"Status Code: {response_status}")
        logger.error(f"Response Text: {response_data}")
        raise ParadexAPIError("Failed to get JWT token")

    async def perform_onboarding(
        self, account_address: str, private_key: str, ethereum_account: str
    ) -> None:
        if not self.config:
            await self.get_config()

        chain_id = int_from_bytes(self.config["starknet_chain_id"].encode())
        account = get_account(account_address, private_key, self.config)

        message = build_onboarding_message(chain_id)
        sig = account.sign_message(message)

        method = "POST"
        path = "/onboarding"

        headers = {
            "PARADEX-ETHEREUM-ACCOUNT": ethereum_account,
            "PARADEX-STARKNET-ACCOUNT": account_address,
            "PARADEX-STARKNET-SIGNATURE": flatten_signature(sig),
        }

        body = {
            "public_key": hex(account.signer.public_key),
            "referral_code": "boldwhale88",
        }

        await self._make_request(
            method, path, headers=headers, data=body, check_jwt=False
        )

    async def get_account_info(self) -> Dict[str, Any]:
        method = "GET"
        path = "/account"
        await self.refresh_token()

        response, success = await self._make_request(method, path)

        response_status = response.status
        response_data = await response.json()

        if success:
            return response_data

        logger.error(f"Unable to [{method}] {path}")
        logger.error(f"Status Code: {response_status}")
        logger.error(f"Response Text: {response_data}")
        raise ParadexAPIError("Failed to get account info")

    async def get_margin_configuration(self, market: str) -> Dict[str, Any]:
        await self.refresh_token()
        method = "GET"
        path = f"/account/margin/?market={market}"

        response, success = await self._make_request(method, path)

        response_status = response.status
        response_data = await response.json()

        if success:
            return response_data

        logger.error(f"Unable to [{method}] {path}")
        logger.error(f"Status Code: {response_status}")
        logger.error(f"Response Text: {response_data}")
        raise ParadexAPIError("Failed to get margin configuration")

    async def set_margin_configuration(
        self, market: str, leverage: int, margin_type: str
    ) -> Dict[str, Any]:
        await self.refresh_token()
        method = "POST"
        path = f"/account/margin/{market}"
        data = {"leverage": leverage, "marginType": margin_type}

        response, success = await self._make_request(method, path, data=data)

        response_status = response.status
        response_data = await response.json()

        if success:
            return response_data

        logger.error(f"Unable to [{method}] {path}")
        logger.error(f"Status Code: {response_status}")
        logger.error(f"Response Text: {response_data}")
        raise ParadexAPIError("Failed to set margin configuration")

    async def place_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        method = "POST"
        path = "/orders"
        await self.refresh_token()

        response, success = await self._make_request(method, path, data=payload)

        response_status = response.status
        response_data = await response.json()

        if success:
            return response_data

        logger.error(f"Unable to [{method}] {path}")
        logger.error(f"Status Code: {response_status}")
        logger.error(f"Response Text: {response_data}")
        raise ParadexAPIError("Failed to place order")

    async def cancel_order(self, order_id: str) -> dict:
        method = "DELETE"
        path = f"/orders/{order_id}"
        await self.refresh_token()
        response, success = await self._make_request(method, path)
        if response.status == 204:
            # Pas de contenu à décoder, retour simple
            return {"status": "cancelled", "order_id": order_id}
        response_data = await response.json()
        if success:
            return response_data
        logger.error(f"Unable to [{method}] {path}")
        logger.error(f"Status Code: {response.status}")
        logger.error(f"Response Text: {response_data}")
        raise ParadexAPIError("Failed to cancel order")

    async def get_order(self, order_id: str) -> Dict[str, Any]:
        await self.refresh_token()
        method = "GET"
        path = f"/orders/{order_id}"
        await self.refresh_token()

        response, success = await self._make_request(method, path)

        response_status = response.status
        response_data = await response.json()

        if success:
            return response_data

        logger.error(f"Unable to [{method}] {path}")
        logger.error(f"Status Code: {response_status}")
        logger.error(f"Response Text: {response_data}")
        raise ParadexAPIError("Failed to get order")

    async def get_bbo(self, market: str) -> Dict[str, Any]:
        method = "GET"
        path = f"/bbo/{market}"

        response, success = await self._make_request(method, path, check_jwt=False)

        response_status = response.status
        response_data = await response.json()

        if success:
            return response_data

        logger.error(f"Unable to [{method}] {path}")
        logger.error(f"Status Code: {response_status}")
        logger.error(f"Response Text: {response_data}")
        raise ParadexAPIError("Failed to get BBO")

    async def get_market_data(self, market: Optional[str] = None) -> Dict[str, Any]:
        method = "GET"
        path = f"/markets/?market={market}" if market else "/markets/"

        response, success = await self._make_request(method, path, check_jwt=False)

        response_status = response.status
        response_data = await response.json()

        if success:
            return response_data["results"][0]

        logger.error(f"Unable to [{method}] {path}")
        logger.error(f"Status Code: {response_status}")
        logger.error(f"Response Text: {response_data}")
        raise ParadexAPIError("Failed to get market data")

    async def update_max_slippage(self, max_slippage: str) -> Dict[str, Any]:
        await self.refresh_token()
        method = "POST"
        path = "/v1/account/profile/max_slippage"
        data = {"max_slippage": max_slippage}

        response, success = await self._make_request(method, path, data=data)

        response_status = response.status
        response_data = await response.json()

        if success:
            return response_data

        logger.error(f"Unable to [{method}] {path}")
        logger.error(f"Status Code: {response_status}")
        logger.error(f"Response Text: {response_data}")
        raise ParadexAPIError("Failed to update max slippage")

    def sign_order(
        self, order: Order) -> str:
        if not self.config:
            raise ParadexAPIError("Config not initialized. Call get_config() first")

        account = get_account(self.account_address, self.private_key, self.config)
        message = build_order_sign_message(
            int_from_bytes(self.config["starknet_chain_id"].encode()), order
        )

        sig = account.sign_message(message)
        return flatten_signature(sig)
    

    async def refresh_token(self):
        if self.last_refresh is None or time.time() - self.last_refresh > 60 * 3:
            logger.debug("refreshing token")
            self.paradex_jwt = await self.get_jwt_token()
            self.last_refresh = time.time()

    async def _check_token_expiry(
        self, status_code: int, response_data: Dict[str, Any]
    ) -> None:
        if is_token_expired(status_code, response_data):
            logger.warning("JWT token has expired, attempting to refresh...")
            if not self.account_address or not self.private_key:
                logger.error(
                    "Cannot refresh token: account_address or private_key not provided"
                )
                raise ParadexAPIError("Token expired and no credentials to refresh")
            await self.get_jwt_token(self.account_address, self.private_key)
            logger.info("JWT token refreshed successfully")

    async def place_limit_order(
        self,
        market: str,
        size: Decimal,
        limit_price: Decimal,
        order_side: OrderSide = OrderSide.Buy,
        order_type: OrderType = OrderType.Limit,
        reduce_only: bool = False,
    ) -> str:
        order = Order(
            market=market,
            order_type=order_type,
            order_side=order_side,
            size=size,
            limit_price=limit_price,
            signature_timestamp=int(time.time()) * 1_000,
            flags=["REDUCE_ONLY"] if reduce_only else [],
        )

        order.signature = self.sign_order(
            order
        )

        order_response = await self.place_order(order.dump_to_dict())
        order_id = order_response["id"]

        created_order = await self.get_order(order_id)

        cancel_reason = created_order.get("cancel_reason")
        if cancel_reason:
            raise OrderCancelError(cancel_reason)

        return order_id

    async def get_balance(self) -> dict:
        await self.refresh_token()
        
        method = "GET"
        path = "/balance"
        response, success = await self._make_request(method, path)
        if not success:
            raise ParadexAPIError("Failed to get balance")
        data = await response.json()
        return data.get('results', [])

    async def get_open_orders(self) -> list:
        await self.refresh_token()
        method = "GET"
        path = "/orders"
        response, success = await self._make_request(method, path)
        if not success:
            raise ParadexAPIError("Failed to get open orders")
        data = await response.json()
        orders = []
        for item in data.get("results", []):
            
                # Conversion des champs string vers Decimal si nécessaire
            item["size"] = Decimal(item["size"])
            item["remaining_size"] = Decimal(item["remaining_size"])
            item["price"] = Decimal(item["price"])
            item["trigger_price"] = Decimal(item.get("trigger_price", "0"))
            orders.append(OrderPlaced(**item))
        return orders
    

    async def cancel_all_open_orders(self) -> None:
        open_orders = await self.get_open_orders()
        for order in open_orders:
            try:
                await self.cancel_order(order.id)
                logger.info(f"Cancelled order {order.id} on market {order.market}")
            except ParadexAPIError as e:
                logger.error(f"Failed to cancel order {order.id}: {str(e)}")
            await asyncio.sleep(0.2)  # To avoid hitting rate limits

    async def get_open_positions(self) -> dict:
        await self.refresh_token()
        
        method = "GET"
        path = "/positions"
        response, success = await self._make_request(method, path)
        if not success:
            raise ParadexAPIError("Failed to get open positions")
        data = await response.json()
        count = 0
        res = []
        for _ in data.get("results", []):
            count += 1
            if count > 10:
                break
            if _.get('status') == 'OPEN':
                pos = Position(
                    id=_.get('id'),
                    market=_.get('market'),
                    size=Decimal(_.get('size')),
                    entryPrice=str(_.get('average_entry_price_usd')),
                    unrealizedPnl=str(_.get('unrealized_pnl')),
                    margin=str(_.get('cost_usd')),
                    leverage=str(_.get('leverage')),
                    liquidationPrice=str(_.get('liquidation_price')),
                    side=OrderSide.Buy if _.get('side') == 'LONG' else OrderSide.Sell,
                    status=_.get('status'),
                    account=_.get('account'),
                )
                res.append(pos)
        return res
    

    async def close_position_limit(self,position : Position,limit_price:str = None) -> str:
        if position.status != 'OPEN':
            logger.error(f"Position {position.id} is not open, cannot close.")
            return ""
        order_side = OrderSide.Sell if position.side == OrderSide.Buy else OrderSide.Buy
        order_id = await self.place_limit_order(
            market=position.market,
            size=position.size,
            limit_price=Decimal(limit_price),
            order_side=order_side,
            order_type=OrderType.Limit,
            reduce_only=True,
        )
        return order_id

