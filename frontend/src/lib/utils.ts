export function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

export function formatCurrency(amount: string, currency: string) {
  const numeric = Number(amount);
  if (!Number.isFinite(numeric)) return `${amount} ${currency}`;
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(numeric);
}

export function compactId(value: string) {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}
