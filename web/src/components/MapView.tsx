import { useMemo, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Polyline, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { useFloodStore } from '../lib/store';
import { cn, getRiskColor, getRiskLabel } from '../lib/utils';
import { wardTooltipHtml } from '../lib/tooltip';
import { isStraightLine } from '../lib/geo';
import type { RiskResponse, RoadRisk, WardRisk } from '../types';

const CHENNAI_BOUNDS: L.LatLngBoundsExpression = [
  [12.84, 80.15],
  [13.24, 80.33],
];

interface MapViewProps {
  className?: string;
}

export function MapView({ className }: MapViewProps) {
  const { wards, riskData, ui, roadRisks, shelters, selectedShelterId, shelterOrigin, setDetailWard } = useFloodStore();
  const geoJsonRef = useRef<L.GeoJSON | null>(null);
  const roadsView = ui.mapView === 'roads';
  const sheltersView = ui.mapView === 'shelters';

  const wardsGeoJSON = useMemo<GeoJSON.FeatureCollection | null>(() => {
    const features = wards
      .filter((ward) => ward.geometry)
      .map((ward) => ({
        type: 'Feature' as const,
        properties: {
          ward_id: ward.ward_id,
          ward_number: ward.ward_number,
          ward_name: ward.ward_name,
          area_sqkm: ward.area_sqkm,
        },
        geometry: ward.geometry!,
      }));
    return features.length > 0 ? { type: 'FeatureCollection', features } : null;
  }, [wards]);

  const riskByWard = useMemo(
    () => new Map(riskData?.wards.map((w) => [w.ward_id, w]) ?? []),
    [riskData]
  );

  const dimmed = roadsView || sheltersView;

  const getWardStyle = (feature?: GeoJSON.Feature): L.PathOptions => {
    const riskWard = riskByWard.get(feature?.properties?.ward_id);
    const selected = feature?.properties?.ward_id === ui.detailWardId;
    if (riskWard) {
      return {
        fillColor: getRiskColor(riskWard.risk_level),
        weight: selected ? 3 : 1,
        opacity: 0.9,
        color: selected ? '#111827' : '#ffffff',
        fillOpacity: dimmed ? 0.25 : 0.7,
      };
    }
    return { fillColor: '#e5e7eb', weight: selected ? 3 : 1, opacity: 0.6, color: selected ? '#111827' : '#6b7280', fillOpacity: 0.3 };
  };

  const onEachFeature = (feature: GeoJSON.Feature, layer: L.Layer) => {
    const props = feature.properties!;
    const path = layer as L.Path;
    path.on({
      click: () => setDetailWard(props.ward_id),
      mouseover: () => {
        path.setStyle({ weight: 3, color: '#1f2937' });
        path.bringToFront();
      },
      mouseout: () => geoJsonRef.current?.resetStyle(path),
    });
    path.bindTooltip(wardTooltipHtml(props as Parameters<typeof wardTooltipHtml>[0], riskByWard.get(props.ward_id)), { sticky: true });
  };

  const selectedShelter = shelters.find((s) => s.shelter_id === selectedShelterId);

  return (
    <div className={cn('flex-1 relative', className)}>
      <MapContainer
        // Fixed Greater Chennai Corporation extent: tiles load once instead of again after the wards arrive.
        bounds={CHENNAI_BOUNDS}
        boundsOptions={{ padding: [8, 8] }}
        scrollWheelZoom={true}
        className="!absolute inset-0 !rounded-none"
      >
        {/* Standard OSM tiles: no API key needed (CARTO's basemaps now return "API key required" tiles). */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />

        {wardsGeoJSON && (
          <GeoJSON
            // remount when inputs change so tooltips and handlers see fresh data
            key={`${riskData?.generated_at ?? 'no-risk'}-${ui.mapView}-${ui.detailWardId}`}
            ref={geoJsonRef}
            data={wardsGeoJSON}
            style={getWardStyle}
            onEachFeature={onEachFeature}
          />
        )}

        {roadsView && <RoadLayer roads={roadRisks} />}

        {sheltersView && (
          <>
            {shelters.map((s) => (
              <CircleMarker
                key={s.shelter_id}
                center={[s.latitude, s.longitude]}
                radius={s.shelter_id === selectedShelterId ? 9 : 6}
                pathOptions={{ color: '#065f46', fillColor: '#10b981', fillOpacity: 0.9, weight: 2 }}
              >
                <Tooltip>{s.name}</Tooltip>
              </CircleMarker>
            ))}
            {shelterOrigin && (
              <CircleMarker
                center={[shelterOrigin.lat, shelterOrigin.lng]}
                radius={7}
                pathOptions={{ color: '#1e3a8a', fillColor: '#3b82f6', fillOpacity: 1, weight: 2 }}
              >
                <Tooltip>{shelterOrigin.label}</Tooltip>
              </CircleMarker>
            )}
            {selectedShelter?.route_geometry?.type === 'LineString' && (
              <Polyline
                positions={selectedShelter.route_geometry.coordinates.map(([lng, lat]) => [lat, lng] as [number, number])}
                pathOptions={{
                  color: '#1d4ed8',
                  weight: 4,
                  dashArray: isStraightLine(selectedShelter.route_geometry) ? '6 8' : undefined,
                }}
              />
            )}
          </>
        )}
      </MapContainer>

      {roadsView ? <RoadLegend roads={roadRisks} /> : <MapLegend riskData={riskData} />}
    </div>
  );
}

function RoadLayer({ roads }: { roads: RoadRisk[] }) {
  return (
    <>
      {roads.map((road) => {
        if (road.geometry.type !== 'LineString') return null;
        const positions = road.geometry.coordinates.map(([lng, lat]) => [lat, lng] as [number, number]);
        const color = getRiskColor(road.risk_level);
        const action = road.risk_level === 'very_high' || road.risk_level === 'high' ? 'Close / divert traffic' : 'Monitor';
        const label = (
          <Tooltip sticky>
            <strong>{road.name}</strong>
            <br />
            {getRiskLabel(road.risk_level)} • ~{road.flood_depth_estimate_m.toFixed(2)} m water
            <br />
            {action}
          </Tooltip>
        );
        if (road.is_underpass) {
          const mid = positions[Math.floor(positions.length / 2)];
          return (
            <CircleMarker key={road.road_id} center={mid} radius={7} pathOptions={{ color: '#111827', weight: 2, fillColor: color, fillOpacity: 1 }}>
              {label}
            </CircleMarker>
          );
        }
        return (
          <Polyline key={road.road_id} positions={positions} pathOptions={{ color, weight: 5, opacity: 0.9 }}>
            {label}
          </Polyline>
        );
      })}
    </>
  );
}

const LEVELS: Array<{ key: WardRisk['risk_level']; label: string }> = [
  { key: 'very_high', label: 'Very High' },
  { key: 'high', label: 'High' },
  { key: 'moderate', label: 'Moderate' },
  { key: 'low', label: 'Low' },
  { key: 'very_low', label: 'Very Low' },
];

function MapLegend({ riskData }: { riskData: RiskResponse | null }) {
  if (!riskData) return null;
  const counts = Object.fromEntries(LEVELS.map(({ key }) => [key, riskData.wards.filter((w) => w.risk_level === key).length]));

  return (
    <div className="absolute bottom-4 left-4 z-10 card p-3 shadow-lg min-w-[160px] animate-in">
      <h2 className="text-sm font-semibold text-gray-900 mb-2">Wards by risk</h2>
      <ul className="space-y-1.5">
        {LEVELS.map(({ key, label }) => (
          <li key={key} className="flex items-center gap-2 text-sm">
            <span className="w-4 h-4 rounded" style={{ backgroundColor: getRiskColor(key) }} aria-hidden="true" />
            <span className="text-gray-800">{label}</span>
            <span className="ml-auto font-mono text-gray-700">{counts[key]}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-gray-600 mt-2 border-t border-gray-100 pt-2">Click a ward for details</p>
    </div>
  );
}

function RoadLegend({ roads }: { roads: RoadRisk[] }) {
  const underpasses = roads.filter((r) => r.is_underpass);
  const closeNow = underpasses.filter((r) => r.risk_level === 'high' || r.risk_level === 'very_high').length;
  return (
    <div className="absolute bottom-4 left-4 z-10 card p-3 shadow-lg w-60 animate-in">
      <h2 className="text-sm font-semibold text-gray-900 mb-1">Roads &amp; underpasses</h2>
      <p className="text-xs text-gray-700">
        {roads.length === 0
          ? 'No road data available for this scenario.'
          : `${underpasses.length} underpasses, ${closeNow} at high risk (consider closing).`}
      </p>
      <ul className="mt-2 space-y-1 text-xs text-gray-800">
        <li className="flex items-center gap-2"><span className="w-5 h-1.5 rounded" style={{ backgroundColor: getRiskColor('high') }} aria-hidden="true" /> Road segment, coloured by risk</li>
        <li className="flex items-center gap-2"><span className="w-3 h-3 rounded-full border-2 border-gray-900" style={{ backgroundColor: getRiskColor('very_high') }} aria-hidden="true" /> Underpass</li>
      </ul>
    </div>
  );
}
