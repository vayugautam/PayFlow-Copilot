from pydantic import BaseModel, Field


class CreateOrderRequest(BaseModel):
    amount: int = Field(..., ge=100, description="Amount in paise")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    receipt: str = Field(..., min_length=1, max_length=40)


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str


class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id: str = Field(..., min_length=1)
    razorpay_order_id: str = Field(..., min_length=1)
    razorpay_signature: str = Field(..., min_length=1)


class VerifyPaymentResponse(BaseModel):
    verified: bool
    message: str


class ReconcilePaymentFailureRequest(BaseModel):
    razorpay_payment_id: str = Field(..., min_length=1)
    razorpay_order_id: str = Field(..., min_length=1)
    error_code: str | None = None
    error_description: str | None = None
    error_source: str | None = None
    error_step: str | None = None
    error_reason: str | None = None


class ReconcilePaymentFailureResponse(BaseModel):
    status: str
    message: str
