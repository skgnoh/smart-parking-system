from abc import ABC, abstractmethod

class PaymentService(ABC):
    @abstractmethod
    async def process_payment(self, plate_num: str, amount: float) -> bool:
        """
        Process the payment for a given plate and amount.
        Returns True if successful, False otherwise.
        """
        pass

class MockPaymentService(PaymentService):
    async def process_payment(self, plate_num: str, amount: float) -> bool:
        """
        Mock implementation. Automatically approves transactions.
        """
        # In a real scenario, this would interface with the TNG reader API.
        print(f"[MOCK PAYMENT] Processing RM {amount:.2f} for plate {plate_num}...")
        print("[MOCK PAYMENT] Transaction successful.")
        return True
