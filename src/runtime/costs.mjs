// Cost accounting: DeepSeek pricing, billing bands, and per-batch cost arithmetic.

// DeepSeek prices in USD per 1,000,000 tokens. Off-peak is exactly half of peak.
// Source: api-docs.deepseek.com/quick_start/pricing, read 2026-09-14.
export const PRICING = {
  cacheHit:  { offPeak: 0.003, peak: 0.006 },
  cacheMiss: { offPeak: 0.15,  peak: 0.30  },
  output:    { offPeak: 0.60,  peak: 1.20  },
};

// Peak hours are 01:00-04:00 and 06:00-10:00 UTC, Monday-Friday. Every other hour is
// off-peak. Billing band is decided per stage from that stage's own start time, because a
// long run can span a boundary.
export const PEAK_UTC_HOURS = [[1, 4], [6, 10]];

export function billingBand(isoTimestamp) {
  const at = new Date(isoTimestamp);
  const weekday = at.getUTCDay() >= 1 && at.getUTCDay() <= 5;
  const hour = at.getUTCHours();
  const inPeakWindow = PEAK_UTC_HOURS.some(([from, to]) => hour >= from && hour < to);
  return weekday && inPeakWindow ? "peak" : "off-peak";
}

export function costForBand(band, { hit = 0, miss = 0, output = 0 }) {
  const key = band === "peak" ? "peak" : "offPeak";
  return (hit / 1e6) * PRICING.cacheHit[key]
    + (miss / 1e6) * PRICING.cacheMiss[key]
    + (output / 1e6) * PRICING.output[key];
}