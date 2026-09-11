import React from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Polygon } from 'react-leaflet';
import L from 'leaflet';
import { useSurveyStore } from '../../store/useSurveyStore';
import { PriorityBadge } from '../shared/PriorityBadge';
import { RefusalBadge } from '../shared/RefusalBadge';
import { DataQualityBadge } from '../shared/DataQualityBadge';
import { MaskOrBoxOutline } from '../shared/MaskOrBoxOutline';
import { MapPin, Navigation, Compass, ShieldAlert, Sparkles } from 'lucide-react';

// Custom Leaflet DivIcon generator matching Ocean Gradient Design
function createCustomPinIcon(threatLevel: string, confidence: number, isNet: boolean, isSelected: boolean) {
  let color = '#4C8C5B';
  if (threatLevel === 'CRITICAL') color = '#B23A2E';
  if (threatLevel === 'HIGH') color = '#C97A1E';
  if (threatLevel === 'MEDIUM') color = '#C9A227';

  const html = `
    <div style="
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: center;
      transform: translate(-50%, -50%);
    ">
      <div style="
        width: ${isSelected ? '28px' : '22px'};
        height: ${isSelected ? '28px' : '22px'};
        background: ${color};
        border: 2px solid ${isSelected ? '#FFFFFF' : '#030A17'};
        border-radius: 50%;
        box-shadow: 0 0 ${isSelected ? '16px' : '8px'} ${color};
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-family: monospace;
        font-size: 10px;
        font-weight: bold;
      ">
        ${isNet ? '★' : `${confidence}%`}
      </div>
    </div>
  `;

  return L.divIcon({
    html,
    className: 'custom-sonar-pin',
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });
}

interface LiveMapPanelProps {
  className?: string;
  isReadOnly?: boolean;
}

export const LiveMapPanel: React.FC<LiveMapPanelProps> = ({
  className = '',
  isReadOnly = false,
}) => {
  const {
    surveys,
    activeSurveyId,
    streamedDetections,
    detections,
    selectedDetectionId,
    setSelectedDetectionId,
  } = useSurveyStore();

  const activeSurvey = surveys.find((s) => s.id === activeSurveyId) || surveys[0];
  const centerPos = activeSurvey.centerCoordinates;

  // Trackpoints for ship path
  const trackCoords: [number, number][] = activeSurvey.trackPoints.map((tp) => [
    tp.latitude,
    tp.longitude,
  ]);

  // Use streamed detections in live mode, or all detections in read-only mode
  const displayedDetections = isReadOnly
    ? detections.filter((d) => d.surveyId === activeSurveyId)
    : streamedDetections.filter((d) => d.surveyId === activeSurveyId);

  // Located detections with valid coordinates
  const locatedDetections = displayedDetections.filter(
    (d): d is typeof d & { position: { kind: 'located'; lat: number; lng: number } } =>
      d.position.kind === 'located'
  );

  // Refused detections (missing navigation)
  const unlocatedDetections = displayedDetections.filter((d) => d.position.kind === 'unlocated');

  // Simulated Marine Protected Area (MPA) Geofence polygon
  const mpaPolygon: [number, number][] = [
    [centerPos[0] - 0.04, centerPos[1] - 0.05],
    [centerPos[0] + 0.05, centerPos[1] - 0.03],
    [centerPos[0] + 0.03, centerPos[1] + 0.05],
    [centerPos[0] - 0.05, centerPos[1] + 0.04],
  ];

  return (
    <div className={`relative flex flex-col glass-panel rounded-xl overflow-hidden p-3 gap-2.5 ${className}`}>
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <Navigation className="w-4 h-4 text-cyan-400" />
          <h3 className="font-heading font-bold text-sm text-white tracking-wide">
            {isReadOnly ? 'GEOSPATIAL SURVEY HAZARDS' : 'REAL-TIME MAP OVERLAY'}
          </h3>
          <span className="text-[10px] font-mono text-cyan-300 bg-cyan-950/80 border border-cyan-500/30 px-1.5 py-0.5 rounded">
            {isReadOnly ? 'COMPLETED' : 'LIVE STREAM'}
          </span>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span>{locatedDetections.length} Pins Overlaid</span>
          </div>
          {unlocatedDetections.length > 0 && (
            <div className="flex items-center gap-1 text-rose-400">
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>{unlocatedDetections.length} Refused (No Nav)</span>
            </div>
          )}
        </div>
      </div>

      {/* Map Area */}
      <div className="relative flex-1 min-h-[340px] rounded-lg overflow-hidden border border-slate-800 bg-[#020712]">
        <MapContainer
          center={centerPos}
          zoom={13}
          scrollWheelZoom={false}
          className="w-full h-full"
        >
          {/* CartoDB Dark Matter ocean basemap */}
          <TileLayer
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          />

          {/* Marine Protected Area Geofence */}
          <Polygon
            positions={mpaPolygon}
            pathOptions={{
              color: '#065A82',
              fillColor: '#1C7293',
              fillOpacity: 0.12,
              weight: 1.5,
              dashArray: '5, 5',
            }}
          />

          {/* Vessel SSS Survey Trackline */}
          <Polyline
            positions={trackCoords}
            pathOptions={{
              color: '#22D3EE',
              weight: 2.5,
              opacity: 0.8,
            }}
          />

          {/* Live Detections Dropped as They Clear Verification */}
          {locatedDetections.map((detection) => {
            const isSelected = selectedDetectionId === detection.id;
            const icon = createCustomPinIcon(
              detection.threatLevel,
              detection.confidencePercent,
              detection.classification === 'entangled_net',
              isSelected
            );

            return (
              <Marker
                key={detection.id}
                position={[detection.position.lat, detection.position.lng]}
                icon={icon}
                eventHandlers={{
                  click: () => setSelectedDetectionId(detection.id),
                }}
              >
                <Popup>
                  <div className="p-1 min-w-[200px] text-xs font-sans space-y-1.5 text-slate-100">
                    <div className="flex items-center justify-between">
                      <PriorityBadge priority={detection.threatLevel} size="sm" />
                      <span className="font-mono text-cyan-400 font-bold">
                        {detection.confidencePercent}% Conf
                      </span>
                    </div>

                    <div className="font-bold text-sm text-white pt-1">
                      {detection.classNameLabel}
                    </div>

                    <div className="flex items-center justify-center bg-black/40 rounded p-2 border border-slate-700">
                      <MaskOrBoxOutline detection={detection} width={120} height={70} />
                    </div>

                    <div className="text-[10px] font-mono text-slate-400 space-y-0.5">
                      <div>Dimensions: {detection.boundingBox.widthM}m × {detection.boundingBox.heightM}m</div>
                      <div>Coords: {detection.position.lat.toFixed(5)}°N, {detection.position.lng.toFixed(5)}°E</div>
                      {detection.errorBudget && (
                        <div className="text-cyan-300">
                          Pos Uncertainty: ±{detection.errorBudget.sigmaPosTotal}m
                        </div>
                      )}
                    </div>

                    {detection.lowDataQuality && (
                      <DataQualityBadge type="low_data_quality" size="sm" />
                    )}
                  </div>
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>

        {/* Unlocated Refusal Strip in Bottom Overlay */}
        {unlocatedDetections.length > 0 && (
          <div className="absolute bottom-2 left-2 z-[400] bg-slate-950/95 border border-rose-500/50 rounded-lg p-2 text-xs font-mono text-slate-300 shadow-2xl backdrop-blur-md max-w-xs">
            <div className="flex items-center gap-1.5 text-rose-400 font-bold border-b border-slate-800 pb-1">
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>REFUSED GEOLOCATIONS ({unlocatedDetections.length})</span>
            </div>
            <div className="pt-1 text-[11px] text-slate-400">
              Structural Refusal Invariant Enforced: Coordinates are null because navigation metadata was missing during ping receipt. Coordinates are never fabricated.
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
