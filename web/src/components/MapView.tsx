import { useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useFloodStore } from '../lib/store';
import { getRiskColor, getDepthColor } from '../lib/utils';
import type { WardRisk, WardFeature } from '../types';
import L from 'leaflet';

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

interface MapViewProps {
  className?: string;
}

export function MapView({ className }: MapViewProps) {
  const { wards, riskData, ui, setSelectedWard, setDetailWard } = useFloodStore();
  const [wardsGeoJSON, setWardsGeoJSON] = useState<GeoJSON.FeatureCollection | null>(null);
  const mapRef = useRef<L.Map | null>(null);

  useEffect(() => {
    if (wards.length > 0 && !wardsGeoJSON) {
      const features = wards.map((ward) => ({
        type: 'Feature' as const,
        properties: {
          ward_id: ward.ward_id,
          ward_number: ward.ward_number,
          ward_name: ward.ward_name,
          area_sqkm: ward.area_sqkm,
        },
        geometry: ward.geometry,
      }));
      setWardsGeoJSON({ type: 'FeatureCollection', features });
    }
  }, [wards, wardsGeoJSON]);

  const getWardStyle = (feature: GeoJSON.Feature) => {
    const wardId = feature.properties.ward_id;
    const riskWard = riskData?.wards.find((w) => w.ward_id === wardId);
    
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

  const handleClick = (e: L.LeafletMouseEvent) => {
    const layer = e.layer as L.GeoJSON;
    if (layer.feature) {
      const wardId = layer.feature.properties.ward_id;
      setDetailWard(wardId);
    }
  };

  const handleHighlight = (e: L.LeafletEvent) => {
    const layer = e.target as L.Path;
    layer.setStyle({
      weight: 3,
      color: '#1f2937',
      fillOpacity: 0.9,
    });
    if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {
      layer.bringToFront();
    }
  };

  const handleResetHighlight = (e: L.LeafletEvent) => {
    const layer = e.target as L.Path;
    const feature = (layer as L.GeoJSON).feature;
    if (feature) {
      layer.setStyle(getWardStyle(feature));
    }
  };

  return (
    <div className={cn('flex-1 relative', className)}>
      <MapContainer
        ref={mapRef}
        center={[13.0827, 80.2707]}
        zoom={11}
        scrollWheelZoom={true}
        className="h-full w-full"
        whenCreated={(map) => {
          mapRef.current = map;
        }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        
        {wardsGeoJSON && (
          <GeoJSON
            data={wardsGeoJSON}
            style={getWardStyle}
            onEachFeature={(feature, layer) => {
              layer.on({
                click: handleClick,
                mouseover: handleHighlight,
                mouseout: handleResetHighlight,
              });
              
              const wardId = feature.properties.ward_id;
              const riskWard = riskData?.wards.find((w) => w.ward_id === wardId);
              
              let popupContent = `
                <div class="p-2 min-w-[200px]">
                  <h3 class="font-semibold text-gray-900">${feature.properties.ward_name}</h3>
                  <p class="text-sm text-gray-500">Ward ${feature.properties.ward_number} • ${feature.properties.area_sqkm.toFixed(2)} km²</p>
              `;
              
              if (riskWard) {
                popupContent += `
                  <hr class="my-1.5 border-gray-200" />
                  <div class="flex items-center gap-2">
                    <span class="w-3 h-3 rounded" style="background-color: ${getRiskColor(riskWard.risk_level)}"></span>
                    <span class="font-medium">${riskWard.risk_level.replace('_', ' ').toUpperCase()}</span>
                  </div>
                  <p class="text-sm text-gray-600 mt-1">Depth: ${riskWard.depth_band}</p>
                  <p class="text-sm text-gray-600">Score: ${(riskWard.risk_score * 100).toFixed(0)}%</p>
                `;
              }
              
              popupContent += '</div>';
              layer.bindPopup(popupContent, { className: 'custom-popup' });
            }}
          />
        )}
      </MapContainer>

      <MapLegend riskData={riskData} />
    </div>
  );
}

import { cn } from '../lib/utils';

function MapLegend({ riskData }: { riskData: import('../types').RiskResponse | null }) {
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
    <div className="absolute bottom-4 left-4 z-20 card p-3 shadow-lg min-w-[160px] animate-in">
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