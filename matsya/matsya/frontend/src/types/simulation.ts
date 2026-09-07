export type Status = "Ready" | "Running" | "Completed" | "Incomplete" | "Error" | "Live" | "Offline";

export interface Area {
  bbox: [number, number, number, number];
  crs: string;
  polygon?: any;
}

export interface RainfallZone {
  id: string;
  amount?: number;
  unit: "rate" | "total";
  mode?: "constant" | "variable";
  points?: { time: number; amount: number }[];
  totalTime?: number;
  maxRain?: number;
  polygon: { type: "Polygon"; coordinates: [number, number][][] };
}

export const ZONE_PALETTE = ["#22d3ee", "#a78bfa", "#f472b6", "#fbbf24", "#34d399", "#fb7185",
  "#60a5fa", "#f97316", "#2dd4bf", "#e879f9", "#a3e635", "#facc15"];

export const MAX_RAIN_ZONES = 12;

export interface Rainfall {
  rateMmHr?: number | null;
  durationHr?: number | null;
  mode?: "constant" | "variable";
  constantRate?: number | null;
  totalTime?: number | null;
  maxRain?: number | null;
  unit?: "rate" | "total" | null;
  points?: {time: number, amount: number}[] | null;
  curve?: {values: number[], method: string, unit: string} | null;
  zones?: RainfallZone[] | null;
}

export interface Terrain {
  demUri?: string | null;
  res?: number | null;
}

export interface Drainage {
  uri?: string | null;
  conduitCount?: number | null;
}

export interface Parameters {
  cfl?: number | null;
  dt?: number | null;
  theta?: number | null;
}

export interface Metadata {
  created: string;
  updated: string;
  status: Status;
}

export interface HydroConfig {
  enabled: boolean;
  version: string;
  drainToWaterbody?: Record<string, string> | null;
  waterbodyStates?: Record<string, any> | null;
  graphStats?: any;
}

export interface Elevation {
  elevationUri?: string | null;
  stats?: any;
  width?: number | null;
  height?: number | null;
}

export interface Flood {
  floodUri?: string | null;
  stats?: any;
  width?: number | null;
  height?: number | null;
  steps?: number | null;
}

export interface Simulation {
  id: string;
  name: string;
  area: { bbox: [number, number, number, number]; crs: string; polygon?: any };
  rainfall: Rainfall;
  status: Status;
  terrain?: any;
  drainage?: any;
  rivers?: any;
  canals?: any;
  waterBodies?: any;
  roads?: any;
  buildings?: any;
  landCover?: any;
  boundaries?: any;
  parameters?: any;
  results?: any;
  elevation?: Elevation | null;
  flood?: Flood | null;
  hydro?: HydroConfig | null;
  metadata?: any;
}
