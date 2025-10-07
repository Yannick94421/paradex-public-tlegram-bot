import math
import time
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel
from typing import List,Optional


class MarketOptionInfoPrice(BaseModel):
    market : str
    ask : Optional[str]
    bid : Optional[str]
    askSize : Optional[str]
    bidSize : Optional[str]

    def spread(self) -> Optional[Decimal]:
        if self.ask is not None and self.bid is not None:
            return float(self.ask) - float(self.bid)
        else:
            return None
    def __repr__(self):
        return f"{self.market} bid:{self.bid} :{self.bidSize} ask:{self.ask} :{self.askSize} spread:{self.spread()}"
    def to_dict(self) -> dict:
        return {
            "market": self.market,
            "ask": self.ask,
            "bid": self.bid,
            "askSize": self.askSize,
            "bidSize": self.bidSize,
            "spread": self.spread()
        }
class OrderBook(BaseModel):
    birds : List[Optional[str]]
    asks : List[Optional[str]]


def time_now_milli_secs() -> float:
    return time.time() * 1_000


def time_now_micro_secs() -> float:
    return time.time() * 1_000_000


class OrderType(Enum):
    Market = "MARKET"
    Limit = "LIMIT"


class OrderSide(Enum):
    Buy = "BUY"
    Sell = "SELL"

    def opposite_side(self):
        if self == OrderSide.Buy:
            return OrderSide.Sell
        else:
            return OrderSide.Buy

    def sign(self) -> int:
        if self == OrderSide.Buy:
            return 1
        else:
            return -1

    def chain_side(self) -> str:
        if self == OrderSide.Buy:
            return "1"
        else:
            return "2"


def quantity_side(amount: Decimal) -> OrderSide:
    if amount >= 0.0:
        return OrderSide.Buy
    else:
        return OrderSide.Sell


def price_more_aggressive(price1: Decimal, price2: Decimal, side: OrderSide) -> bool:
    if side == OrderSide.Buy:
        return price1 > price2
    else:
        return price1 < price2


def sign(a) -> int:
    if a > 0.000001:
        return 1
    elif a < -0.000001:
        return -1
    else:
        return 0


def time_millis() -> int:
    return int(time.time_ns() / 1_000_000)


class OrderStatus(Enum):
    NEW = "NEW"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


def round_to_tick(value, tick):
    return round(value / tick, 0) * tick


def round_to_tick_with_side(value, tick: Decimal, side: OrderSide) -> Decimal:
    if side == OrderSide.Buy:
        return math.floor(value / tick) * tick
    else:
        return math.ceil(value / tick) * tick


def cap_price(
    price: Decimal, most_aggressive_price: Decimal, side: OrderSide
) -> Decimal:
    if side == OrderSide.Buy:
        if isinstance(
            most_aggressive_price, Decimal
        ) and most_aggressive_price != Decimal("0"):
            return price.min(most_aggressive_price)
        else:
            return price
    else:
        if isinstance(
            most_aggressive_price, Decimal
        ) and most_aggressive_price != Decimal("0"):
            return price.max(most_aggressive_price)
        else:
            return price


def add_price_offset(price: Decimal, offset: Decimal, side: OrderSide) -> Decimal:
    if not offset or price is None:
        return price
    else:
        return price + side.sign() * offset


def calc_price_offset(
    target_price: Decimal, price: Decimal, side: OrderSide
) -> Decimal:
    return Decimal(side.sign() * (target_price - price))


class OrderAction(Enum):
    NAN = "NAN"
    Send = "SEND"
    SendCancel = "SEND_CANCEL"


class Order:
    def __init__(
        self,
        market,
        order_type: OrderType,
        order_side: OrderSide,
        size: Decimal,
        limit_price: Decimal | None = None,
        client_id: str = "",
        signature_timestamp=None,
        instruction: str = "GTC",
        flags: list = [],
    ):
        ts = time_millis()
        self.id: str = ""
        self.account: str = ""
        self.status = OrderStatus.NEW
        self.limit_price = limit_price
        self.size = size
        self.market = market
        self.remaining = size
        self.order_type = order_type
        self.order_side = order_side
        self.client_id = client_id
        self.created_at = ts
        self.cancel_reason = ""
        self.last_action = OrderAction.NAN
        self.last_action_time = 0
        self.cancel_attempts = 0
        self.signature = ""
        self.signature_timestamp = (
            ts if signature_timestamp is None else signature_timestamp
        )
        self.instruction = instruction
        self.flags = flags

    def __repr__(self):
        ord_status = self.status.value
        if self.status == OrderStatus.CLOSED:
            ord_status += f"({self.cancel_reason})"
        msg = f"{self.market} {ord_status} {self.order_type.name} "
        msg += f"{self.order_side} {self.remaining}/{self.size}"
        msg += f"@{self.limit_price}" if self.order_type == OrderType.Limit else ""
        msg += f";{self.instruction}"
        msg += f";id={self.id}" if self.id else ""
        msg += f";client_id={self.client_id}" if self.client_id else ""
        msg += (
            f";last_action:{self.last_action}"
            if self.last_action != OrderAction.NAN
            else ""
        )
        msg += f";signed with:{self.signature}@{self.signature_timestamp}"
        if self.flags:
            msg += f";flags={self.flags}"
        return msg

    def __eq__(self, __o) -> bool:
        return self.id == __o.id

    def __hash__(self):
        return hash(self.id)

    def dump_to_dict(self) -> dict:
        order_dict = {
            "market": self.market,
            "side": self.order_side.value,
            "size": str(self.size),
            "type": self.order_type.value,
            "client_id": self.client_id,
            "signature": self.signature,
            "signature_timestamp": self.signature_timestamp,
            "instruction": self.instruction,
        }
        if self.order_type == OrderType.Limit:
            order_dict["price"] = str(self.limit_price)
        if self.flags:
            order_dict["flags"] = self.flags

        return order_dict

    def chain_price(self) -> str:
        if self.order_type == OrderType.Limit:
            if self.limit_price is None:
                raise ValueError(f"Limit order {self.market} has no limit price")
            return str(int(self.limit_price.scaleb(8)))

        return "0"

    def chain_size(self) -> str:
        return str(int(self.size.scaleb(8)))

class Position(BaseModel):
    id: str
    account: str
    status : str
    market: str
    size: Decimal
    entryPrice: str
    unrealizedPnl: str
    realizedPnl: str = "0"
    margin: str = None
    leverage: str = "1"
    liquidationPrice: Optional[str] = None
    markPrice: str = None
    side: OrderSide = OrderSide.Buy

    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "account": self.account,
            "status": self.status,
            "market": self.market,
            "size": str(self.size),
            "entryPrice": str(self.entryPrice),
            "unrealizedPnl": str(self.unrealizedPnl),
            "realizedPnl": str(self.realizedPnl),
            "margin": str(self.margin) if self.margin is not None else None,
            "leverage": str(self.leverage),
            "liquidationPrice": str(self.liquidationPrice) if self.liquidationPrice is not None else None,
            "markPrice": str(self.markPrice) if self.markPrice is not None else None,
            "side": self.side.value
        }
    



class OrderPlaced(BaseModel):
    id: str
    account: str
    market: str
    side: str
    type: str
    size: Decimal
    remaining_size: Decimal
    price: Decimal
    status: str
    created_at: int
    last_updated_at: int
    timestamp: int
    cancel_reason: Optional[str] = ""
    client_id: Optional[str] = ""
    seq_no: Optional[int] = None
    instruction: Optional[str] = ""
    avg_fill_price: Optional[str] = ""
    stp: Optional[str] = ""
    received_at: Optional[int] = None
    published_at: Optional[int] = None
    flags: Optional[List[str]] = []
    trigger_price: Optional[Decimal] = Decimal("0")



    
class Trade(BaseModel):
    price : str
    size : str
    side : str
    time : str

    def __str__(self):
        return f"{self.time} {self.side} {self.size}@{self.price}"
    
