export type Status = "Ready" | "Running" | "Completed" | "Incomplete" | "Error" | "Live" | "Offline";

export interface Area {
  bbox: [number, number, number, number];
  crs: string;
  polygon?: any;
}

export interface Rainfall {
  rateMmHr: number;
  durationHr: number;
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
  rainfall: { rateMmHr: number; durationHr: number };
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
