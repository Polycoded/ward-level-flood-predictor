import { useState, useEffect } from 'react';
import { useFloodStore } from '../lib/store';
import { api } from '../api/client';
import { cn, formatDistance, formatTime } from '../lib/utils';
import type { Shelter } from '../types';

export function ShelterPanel() {
  const { setMapView } = useFloodStore();
  const [shelters, setShelters] = useState<Shelter[]>([]);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        () => setUserLocation({ lat: 13.0827, lng: 80.2707 })
      );
    } else {
      setUserLocation({ lat: 13.0827, lng: 80.2707 });
    }
  }, []);

  const loadShelters = async () => {
    if (!userLocation) return;
    setLoading(true);
    try {
      const data = await api.findShelters(userLocation.lat, userLocation.lng, 10, 10);
      setShelters(data);
    } catch (error) {
      console.error('Failed to load shelters:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadShelters();
  }, [userLocation]);

  return (
    <div className="fixed bottom-0 left-0 right-0 z-[45] bg-white border-t border-gray-200 rounded-t-2xl shadow-xl max-h-[60vh] flex flex-col lg:fixed lg:bottom-4 lg:left-auto lg:right-4 lg:top-4 lg:w-96 lg:rounded-xl lg:max-h-[calc(100vh-2rem)] lg:shadow-2xl">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h2 className="font-semibold text-gray-900 flex items-center gap-2">
          <svg className="w-5 h-5 text-flood-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
          </svg>
          Nearby Shelters
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={loadShelters}
            disabled={loading}
            className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
            title="Refresh"
          >
            <svg className={cn('w-5 h-5', loading && 'animate-spin')} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          <button
            onClick={() => setMapView('risk')}
            className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {userLocation && (
          <div className="text-xs text-gray-500 flex items-center gap-1">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
            </svg>
            Your location: {userLocation.lat.toFixed(4)}, {userLocation.lng.toFixed(4)}
          </div>
        )}

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-gray-100 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : shelters.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <svg className="w-12 h-12 mx-auto text-gray-300 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
            </svg>
            <p>No shelters found nearby</p>
          </div>
        ) : (
          shelters.map((shelter) => (
            <ShelterCard key={shelter.shelter_id} shelter={shelter} onSelect={() => {}} />
          ))
        )}
      </div>
    </div>
  );
}

function ShelterCard({ shelter, onSelect }: { shelter: Shelter; onSelect: () => void }) {
  return (
    <div className="card p-4 hover:shadow-md transition-shadow cursor-pointer" onClick={onSelect}>
      <div className="flex items-start gap-3">
        <div className="w-12 h-12 rounded-lg bg-flood-100 flex items-center justify-center flex-shrink-0">
          <svg className="w-6 h-6 text-flood-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900 truncate">{shelter.name}</h3>
          <p className="text-xs text-gray-500">Capacity: {shelter.capacity} people</p>
          <div className="flex items-center gap-3 mt-2 text-sm text-gray-600">
            <span className="flex items-center gap-1">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
              </svg>
              {formatDistance(shelter.distance_km * 1000)}
            </span>
            <span className="flex items-center gap-1">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {formatTime(shelter.walking_time_min)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}