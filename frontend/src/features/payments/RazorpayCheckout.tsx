import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui";
import { api, getApiError } from "../../lib/api";

type CreateOrderResponse = {
  order_id: string;
  amount: number;
  currency: string;
};

type VerifyPaymentResponse = {
  verified: boolean;
  message: string;
};

type ReconcileFailureResponse = {
  status: "failed" | "pending";
  message: string;
};

const keyId = import.meta.env.VITE_RAZORPAY_KEY_ID as string | undefined;

export function RazorpayCheckout() {
  const queryClient = useQueryClient();
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function startCheckout() {
    setIsLoading(true);
    setMessage(null);
    try {
      const { data: order } = await api.post<CreateOrderResponse>("/payments/create-order", {
        amount: 10000,
        currency: "INR",
        receipt: `payflow-${Date.now()}`,
      });
      if (!keyId || !window.Razorpay) {
        throw new Error("Payment checkout is not available in this browser.");
      }

      const checkout = new window.Razorpay({
        key: keyId,
        amount: order.amount,
        currency: order.currency,
        name: "PayFlow Copilot",
        description: "Test checkout",
        order_id: order.order_id,
        handler: async (response) => {
          try {
            const { data } = await api.post<VerifyPaymentResponse>("/payments/verify-payment", response);
            await queryClient.invalidateQueries({ queryKey: ["transactions"] });
            setMessage(data.message);
          } catch (error) {
            setMessage(getApiError(error, "Payment verification failed."));
          } finally {
            setIsLoading(false);
          }
        },
        modal: {
          ondismiss: () => {
            setMessage("Payment cancelled.");
            setIsLoading(false);
          },
        },
        theme: { color: "#2563eb" },
      });
      checkout.on("payment.failed", async ({ error }) => {
        const paymentId = error?.metadata?.payment_id;
        const orderId = error?.metadata?.order_id ?? order.order_id;
        if (!paymentId) {
          setMessage("Payment failed; awaiting provider verification.");
          setIsLoading(false);
          return;
        }
        try {
          const { data } = await api.post<ReconcileFailureResponse>("/payments/reconcile-failure", {
            razorpay_payment_id: paymentId,
            razorpay_order_id: orderId,
            error_code: error?.code,
            error_description: error?.description,
            error_source: error?.source,
            error_step: error?.step,
            error_reason: error?.reason,
          });
          await queryClient.invalidateQueries({ queryKey: ["transactions"] });
          setMessage(data.message);
        } catch (reconciliationError) {
          setMessage(getApiError(reconciliationError, "Payment failed; awaiting provider verification."));
        } finally {
          setIsLoading(false);
        }
      });
      checkout.open();
    } catch (error) {
      setMessage(getApiError(error, "Unable to start checkout."));
      setIsLoading(false);
    }
  }

  return (
    <div>
      <Button onClick={() => void startCheckout()} disabled={isLoading}>
        {isLoading ? "Opening checkout…" : "Pay ₹100 test amount"}
      </Button>
      {message && <p className="muted" role="status">{message}</p>}
    </div>
  );
}
