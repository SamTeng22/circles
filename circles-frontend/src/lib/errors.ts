/** True for expected, transient failures (rate limits, storage/AI quota) that
 * should read as "try again shortly" rather than "something's broken." */
export function isThrottleMessage(message: string): boolean {
  const m = message.toLowerCase();
  return (
    m.includes("rate limit") ||
    m.includes("quota") ||
    m.includes("usage limit") ||
    m.includes("temporarily unavailable")
  );
}
