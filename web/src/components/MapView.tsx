import { useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useFloodStore } from '../lib/store';
import { cn, getRiskColor } from '../lib/utils';
import type { RiskResponse } from '../types';
import L from 'leaflet';

delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

interface MapViewProps {
  className?: string;
}

export function MapView({ className }: MapViewProps) {
  const { wards, riskData, setDetailWard } = useFloodStore();
  const geoJsonRef = useRef<L.GeoJSON | null>(null);

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

  const getWardStyle = (feature?: GeoJSON.Feature): L.PathOptions => {
    const riskWard = riskByWard.get(feature?.properties?.ward_id);

    if (riskWard) {
      return {
        fillColor: getRiskColor(riskWard.risk_level),
        weight: 1.5,
        opacity: 0.8,
        color: '#ffffff',
        fillOpacity: 0.7,
      };
    }

    return {
      fillColor: '#e5e7eb',
      weight: 1,
      opacity: 0.5,
      color: '#9ca3af',
      fillOpacity: 0.4,
    };
  };

  const onEachFeature = (feature: GeoJSON.Feature, layer: L.Layer) => {
    const props = feature.properties!;
    const path = layer as L.Path;

    path.on({
      click: () => setDetailWard(props.ward_id),
      mouseover: () => {
        path.setStyle({ weight: 3, color: '#1f2937', fillOpacity: 0.9 });
        path.bringToFront();
      },
      mouseout: () => geoJsonRef.current?.resetStyle(path),
    });

    const riskWard = riskByWard.get(props.ward_id);
    let tooltip = `<strong>${props.ward_name}</strong><br/>Ward ${props.ward_number} • ${props.area_sqkm.toFixed(2)} km²`;
    if (riskWard) {
      tooltip += `<br/><span style="color:${getRiskColor(riskWard.risk_level)};font-weight:600">${riskWard.risk_level.replace('_', ' ').toUpperCase()}</span>`
        + ` • ${(riskWard.risk_score * 100).toFixed(0)}% • ${riskWard.depth_band}`;
    }
    path.bindTooltip(tooltip, { sticky: true });
  };

  return (
    <div className={cn('flex-1 relative', className)}>
      <MapContainer
        center={[13.0827, 80.2707]}
        zoom={11}
        scrollWheelZoom={true}
        className="!absolute inset-0 !rounded-none"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {wardsGeoJSON && (
          <GeoJSON
            // remount when risk changes so tooltips and handlers see fresh data
            key={riskData?.generated_at ?? 'no-risk'}
            ref={geoJsonRef}
            data={wardsGeoJSON}
            style={getWardStyle}
            onEachFeature={onEachFeature}
          />
        )}
        {wardsGeoJSON && <FitToWards data={wardsGeoJSON} />}
      </MapContainer>

      <MapLegend riskData={riskData} />
    </div>
  );
}

function FitToWards({ data }: { data: GeoJSON.FeatureCollection }) {
  const map = useMap();
  useEffect(() => {
    const bounds = L.geoJSON(data).getBounds();
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [16, 16] });
  }, [data, map]);
  return null;
}

function MapLegend({ riskData }: { riskData: RiskResponse | null }) {
  if (!riskData) return null;

  const { wards } = riskData;
  const counts = {
    very_high: wards.filter((w) => w.risk_level === 'very_high').length,
    high: wards.filter((w) => w.risk_level === 'high').length,
    moderate: wards.filter((w) => w.risk_level === 'moderate').length,
    low: wards.filter((w) => w.risk_level === 'low').length,
    very_low: wards.filter((w) => w.risk_level === 'very_low').length,
  };

  const levels: Array<{ key: keyof typeof counts; label: string; color: string }> = [
    { key: 'very_high', label: 'Very High', color: '#ef4444' },
    { key: 'high', label: 'High', color: '#f97316' },
    { key: 'moderate', label: 'Moderate', color: '#f59e0b' },
    { key: 'low', label: 'Low', color: '#84cc16' },
    { key: 'very_low', label: 'Very Low', color: '#10b981' },
  ];

  return (
    <div className="absolute bottom-4 left-4 z-10 card p-3 shadow-lg min-w-[160px] animate-in">
      <h4 className="font-semibold text-gray-900 mb-2">Risk Legend</h4>
      <div className="space-y-1.5">
        {levels.map(({ key, label, color }) => (
          <div key={key} className="flex items-center gap-2 text-sm">
            <span className="w-4 h-4 rounded" style={{ backgroundColor: color }}></span>
            <span className="text-gray-700">{label}</span>
            <span className="ml-auto font-mono text-gray-500">{counts[key]}</span>
          </div>
        ))}
      </div>
      <p className="text-xs text-gray-500 mt-2 border-t border-gray-100 pt-2">
        Click ward for details →
      </p>
    </div>
  );
}
