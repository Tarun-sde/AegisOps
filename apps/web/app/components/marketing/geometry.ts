export type Point = { x: number; y: number };
export type Box = Point & { width: number; height: number };
export const selectionBox = (a: Point, b: Point): Box => ({
  x: Math.min(a.x, b.x),
  y: Math.min(a.y, b.y),
  width: Math.abs(b.x - a.x),
  height: Math.abs(b.y - a.y),
});
export const overlaps = (a: Box, b: Box) =>
  a.x <= b.x + b.width &&
  a.x + a.width >= b.x &&
  a.y <= b.y + b.height &&
  a.y + a.height >= b.y;
export function drawingPoint(
  client: Point,
  rect: Box,
  width = 1000,
  height = 620,
): Point {
  const scale = Math.min(rect.width / width, rect.height / height);
  return {
    x: (client.x - rect.x - (rect.width - width * scale) / 2) / scale,
    y: (client.y - rect.y - (rect.height - height * scale) / 2) / scale,
  };
}
export const issues = [
  {
    x: 410,
    y: 320,
    code: "SIGNAL / 01",
    title: "Illustrative elevated error signal",
    short: "ERROR SIGNAL",
  },
  {
    x: 250,
    y: 440,
    code: "SIGNAL / 02",
    title: "Illustrative latency signal",
    short: "LATENCY SIGNAL",
  },
  {
    x: 580,
    y: 200,
    code: "SIGNAL / 03",
    title: "Illustrative dependency signal",
    short: "DEPENDENCY SIGNAL",
  },
];
