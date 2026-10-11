/**
 * Multi-seat ModernTex pricing (labs and departments). One source of truth for the checkout function;
 * site/moderntex/seats.js carries the same table for the live price display, and a test keeps the two equal.
 *
 * Seats are bought in fixed packs (5, 10, 15, 20) or as any number from 25 up to MAX_SEATS. Every seat in
 * the order is charged the unit price of its tier, so 32 seats cost 32 x the 25-and-over price. One seat
 * is the ordinary $19.99 product, so counts below 5 are rejected here.
 */
export const SEAT_PACKS = [
  { seats: 5, unitCents: 1399 },
  { seats: 10, unitCents: 1249 },
  { seats: 15, unitCents: 1149 },
  { seats: 20, unitCents: 1049 },
];
export const SEAT_BULK = { minSeats: 25, unitCents: 999 };
export const MAX_SEATS = 500;

/** Price per seat in cents for a seat count, or null when the count is not offered. */
export function seatUnitCents(seats) {
  if (!Number.isInteger(seats)) return null;
  const pack = SEAT_PACKS.find((p) => p.seats === seats);
  if (pack) return pack.unitCents;
  if (seats >= SEAT_BULK.minSeats && seats <= MAX_SEATS) return SEAT_BULK.unitCents;
  return null;
}

/** Order total in cents, or null when the count is not offered. */
export function seatTotalCents(seats) {
  const unit = seatUnitCents(seats);
  return unit === null ? null : unit * seats;
}

/** Parse a seat count from untrusted input (number or numeric string); NaN-safe. */
export function parseSeats(value) {
  const n = typeof value === "string" && /^\d{1,4}$/.test(value.trim()) ? Number(value.trim()) : value;
  return Number.isInteger(n) ? n : null;
}
