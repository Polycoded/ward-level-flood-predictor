/** Centre of a ward's bounding box — good enough as a starting point for shelter search. */
export function geometryCenter(geometry: GeoJSON.Geometry | undefined): { lat: number; lng: number } | null {
  if (!geometry) return null;
  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLng = Infinity;
  let maxLng = -Infinity;
  const visit = (coords: unknown): void => {
    if (Array.isArray(coords) && typeof coords[0] === 'number' && typeof coords[1] === 'number') {
      const [lng, lat] = coords as number[];
      minLat = Math.min(minLat, lat);
      maxLat = Math.max(maxLat, lat);
      minLng = Math.min(minLng, lng);
      maxLng = Math.max(maxLng, lng);
    } else if (Array.isArray(coords)) {
      coords.forEach(visit);
    }
  };
  if (geometry.type === 'GeometryCollection') geometry.geometries.forEach((g) => visit('coordinates' in g ? g.coordinates : []));
  else visit(geometry.coordinates);
  if (!Number.isFinite(minLat)) return null;
  return { lat: (minLat + maxLat) / 2, lng: (minLng + maxLng) / 2 };
}

/** OpenStreetMap walking directions, for handing the route to a phone. */
export function osmWalkingDirectionsUrl(from: { lat: number; lng: number }, to: { lat: number; lng: number }): string {
  const fmt = (p: { lat: number; lng: number }) => `${p.lat.toFixed(5)},${p.lng.toFixed(5)}`;
  return `https://www.openstreetmap.org/directions?engine=fossgis_osrm_foot&route=${fmt(from)};${fmt(to)}`;
}

export function isStraightLine(geometry: GeoJSON.Geometry | undefined): boolean {
  return !geometry || (geometry.type === 'LineString' && geometry.coordinates.length <= 2);
}
