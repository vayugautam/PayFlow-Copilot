import { forwardRef, type ButtonHTMLAttributes, type PropsWithChildren } from "react";

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement>>(
  function Button({ className = "", ...props }, ref) {
    return <button ref={ref} className={`button ${className}`} {...props} />;
  },
);

export function Card({ className = "", children }: PropsWithChildren<{ className?: string }>) {
  return <section className={`card ${className}`}>{children}</section>;
}

export function StatusPill({ status }: { status: string }) {
  return <span className={`status status-${status.toLowerCase()}`}>{status.replaceAll("_", " ")}</span>;
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="empty-state"><strong>{title}</strong><span>{description}</span></div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="error-state"><strong>Unable to load this data</strong><span>{message}</span><button onClick={onRetry}>Retry</button></div>;
}
