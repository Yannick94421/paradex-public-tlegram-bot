class ParadexAPIError(Exception):
    def __init__(
        self, message: str = "An error occurred while interacting with Paradex API"
    ) -> None:
        self.message = message
        super().__init__(self.message)

class OrderNotFoundError(Exception):
    def __init__(self, order_id: str) -> None:
        self.message = f"Order with ID {order_id} not found."
        super().__init__(self.message)

class OrderCancelError(Exception):
    def __init__(self, order_id: str) -> None:
        self.message = f"Failed to cancel order with ID {order_id}."
        super().__init__(self.message)