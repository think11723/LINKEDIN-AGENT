export function formatDateTime(value, fallback = '—') {
  if (!value) return fallback;
  try {
    return new Date(value).toLocaleString();
  } catch {
    return fallback;
  }
}

export function toLocalDateTimeInputValue(value) {
  if (!value) return '';
  try {
    const date = new Date(value);
    const tzOffset = date.getTimezoneOffset() * 60_000;
    return new Date(date.getTime() - tzOffset).toISOString().slice(0, 16);
  } catch {
    return '';
  }
}