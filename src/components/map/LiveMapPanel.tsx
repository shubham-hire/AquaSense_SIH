import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useSurveyStore } from '../../store/useSurveyStore';
import { PriorityBadge } from '../shared/PriorityBadge';
import { RefusalBadge } from '../shared/RefusalBadge';
import { DataQualityBadge } from '../shared/DataQualityBadge';
import { MaskOrBoxOutline } from '../shared/MaskOrBoxOutline';
import { Navigation, ShieldAlert, LoaderCircle, MapPinOff, Hand, Grab, LocateFixed, X } from 'lucide-react';

function MapViewport({ trackCoords }: { trackCoords: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (trackCoords.length === 1) {
      map.setView(trackCoords[0], 15, { animate: true });
    } else if (trackCoords.length > 1) {
      map.fitBounds(trackCoords, { padding: [28, 28], maxZoom: 15, animate: true });
    } else {
      map.setView([0, 0], 2, { animate: false });
    }
  }, [map, trackCoords]);
  return null;
}

function MapInteractionListener({
  onHoverChange,
  onDragChange,
}: {
  onHoverChange: (hovering: boolean) => void;
  onDragChange: (dragging: boolean) => void;
}) {
  const map = useMap();

  useEffect(() => {
    const container = map.getContainer();

    const handleMouseEnter = () => onHoverChange(true);
    const handleMouseLeave = () => {
      onHoverChange(false);
      onDragChange(false);
    };

    const handleDragStart = () => onDragChange(true);
    const handleDragEnd = () => onDragChange(false);

    container.addEventListener('mouseenter', handleMouseEnter);
    container.addEventListener('mouseleave', handleMouseLeave);
    map.on('dragstart', handleDragStart);
    map.on('dragend', handleDragEnd);

    return () => {
      container.removeEventListener('mouseenter', handleMouseEnter);
      container.removeEventListener('mouseleave', handleMouseLeave);
      map.off('dragstart', handleDragStart);
      map.off('dragend', handleDragEnd);
    };
  }, [map, onHoverChange, onDragChange]);

  return null;
}

function MapControls({
  trackCoords,
  centerPos,
  hasNavigation,
}: {
  trackCoords: [number, number][];
  centerPos: [number, number];
  hasNavigation: boolean;
}) {
  const map = useMap();

  const handleRecenter = () => {
    if (trackCoords.length === 1) {
      map.setView(trackCoords[0], 15, { animate: true });
    } else if (trackCoords.length > 1) {
      map.fitBounds(trackCoords, { padding: [28, 28], maxZoom: 15, animate: true });
    } else {
      map.setView(centerPos[0] === 0 && centerPos[1] === 0 ? [20, 0] : centerPos, hasNavigation ? 13 : 2, { animate: true });
    }
  };

  return (
    <div className="leaflet-top leaflet-right" style={{ pointerEvents: 'auto', marginTop: '10px', marginRight: '10px' }}>
      <button
        onClick={(e) => {
          e.stopPropagation();
          handleRecenter();
        }}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-slate-900/90 hover:bg-slate-800 border border-slate-700/80 hover:border-cyan-500/50 text-slate-300 hover:text-cyan-300 text-xs font-mono shadow-lg transition backdrop-blur-md cursor-pointer"
        title="Recenter map view"
      >
        <LocateFixed className="w-3.5 h-3.5 text-cyan-400" />
        <span>Recenter</span>
      </button>
    </div>
  );
}

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
        border: 2px solid ${isSelected ? '#FFFFFF' : '#142238'};
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
    activeSurveyId,
    streamedDetections,
    detections,
    selectedDetectionId,
    setSelectedDetectionId,
    navigationBySurvey,
  } = useSurveyStore();

  const [isHovering, setIsHovering] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [dismissNavPrompt, setDismissNavPrompt] = useState(false);

  const navigation = navigationBySurvey[activeSurveyId];
  const trackCoords = useMemo<[number, number][]>(
    () => navigation?.trackPoints.map((point) => [point.latitude, point.longitude]) ?? [],
    [navigation]
  );
  const centerPos: [number, number] = navigation?.mapCenter ?? [0, 0];
  const hasNavigation = navigation?.status === 'ready' && trackCoords.length > 0;

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

  return (
    <div className={`relative flex flex-col glass-panel rounded-xl overflow-hidden p-3 gap-2.5 ${className}`}>
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <Navigation className="w-4 h-4 text-cyan-400" />
          <h3 className="font-heading font-bold text-sm text-white tracking-wide">
            {isReadOnly ? 'GEOSPATIAL SURVEY HAZARDS' : 'REAL-TIME MAP OVERLAY'}
          </h3>
          <span className={`text-[10px] font-mono border px-1.5 py-0.5 rounded ${hasNavigation ? 'text-emerald-300 bg-emerald-950/70 border-emerald-500/30' : 'text-amber-300 bg-amber-950/50 border-amber-500/30'}`}>
            {hasNavigation ? 'SOURCE NAVIGATION' : navigation?.status === 'loading' ? 'LOADING NAVIGATION' : 'NO SOURCE NAV'}
          </span>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
          <div className="flex items-center gap-1"><span className={`w-2 h-2 rounded-full ${hasNavigation ? 'bg-emerald-400' : 'bg-slate-500'}`} /><span>{hasNavigation ? `${trackCoords.length} Source Fixes` : 'No Valid Fixes'}</span></div>
          {unlocatedDetections.length > 0 && (
            <div className="flex items-center gap-1 text-rose-400">
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>{unlocatedDetections.length} Refused (No Nav)</span>
            </div>
          )}
        </div>
      </div>

      {/* Map Area */}
      <div className="relative flex-1 min-h-[340px] rounded-lg overflow-hidden border border-slate-700 bg-[#111A2A]">
        {/* Hand Logo & Pan Mode Indicator on Map Hover */}
        <div
          className={`absolute top-3 left-14 z-[400] pointer-events-none transition-all duration-200 flex items-center gap-2.5 px-3 py-1.5 rounded-lg border backdrop-blur-md shadow-2xl ${
            isDragging
              ? 'bg-cyan-950/95 border-cyan-400 text-cyan-200 shadow-cyan-500/30 scale-105 opacity-100 translate-y-0'
              : isHovering
              ? 'bg-slate-900/95 border-cyan-500/50 text-cyan-300 shadow-black/50 opacity-100 translate-y-0'
              : 'opacity-0 -translate-y-1 pointer-events-none'
          }`}
        >
          <div className="p-1.5 rounded-md bg-cyan-500/20 text-cyan-400 flex items-center justify-center">
            {isDragging ? (
              <Grab className="w-4 h-4 text-cyan-300 animate-pulse" />
            ) : (
              <Hand className="w-4 h-4 text-cyan-400 animate-pulse" />
            )}
          </div>
          <div className="flex flex-col">
            <span className="text-[11px] font-heading font-bold uppercase tracking-wider text-white flex items-center gap-1.5">
              <span>{isDragging ? 'Panning Map' : 'Hand Tool Active'}</span>
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
            </span>
            <span className="text-[10px] font-mono text-cyan-300/80">
              {isDragging ? 'Moving view position…' : 'Click & drag to move map'}
            </span>
          </div>
        </div>

        <MapContainer
          center={centerPos}
          zoom={hasNavigation ? 13 : 2}
          dragging={true}
          scrollWheelZoom={true}
          doubleClickZoom={true}
          className="w-full h-full cursor-grab active:cursor-grabbing"
        >
          <MapViewport trackCoords={trackCoords} />
          <MapInteractionListener onHoverChange={setIsHovering} onDragChange={setIsDragging} />
          <MapControls trackCoords={trackCoords} centerPos={centerPos} hasNavigation={hasNavigation} />

          {/* CartoDB Dark Matter ocean basemap */}
          <TileLayer
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          />

          {trackCoords.length > 1 && (
            <Polyline
              positions={trackCoords}
              pathOptions={{
                color: '#22D3EE',
                weight: 2.5,
                opacity: 0.8,
              }}
            />
          )}

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

        {/* Non-blocking Navigation Status Overlay */}
        {!hasNavigation && !dismissNavPrompt && (
          <div className="absolute inset-0 z-[350] pointer-events-none flex items-center justify-center p-5 text-center">
            <div className="max-w-sm rounded-xl border border-slate-600/70 bg-slate-950/90 p-4 shadow-2xl pointer-events-auto backdrop-blur-md relative">
              <button
                onClick={() => setDismissNavPrompt(true)}
                className="absolute top-2.5 right-2.5 text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition cursor-pointer"
                title="Dismiss notice to explore map freely"
              >
                <X className="w-4 h-4" />
              </button>
              {navigation?.status === 'loading' ? (
                <LoaderCircle className="mx-auto mb-2 h-5 w-5 animate-spin text-cyan-300" aria-hidden="true" />
              ) : (
                <MapPinOff className="mx-auto mb-2 h-5 w-5 text-amber-300" aria-hidden="true" />
              )}
              <p className="text-xs font-semibold text-slate-100">
                {navigation?.status === 'loading' ? 'Loading source navigation…' : 'No survey track loaded'}
              </p>
              <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
                {navigation?.status === 'error'
                  ? navigation.error
                  : 'Upload an XTF, JSF, or SL2 file containing navigation fixes. You can pan and drag anywhere on the ocean map freely with the hand tool.'}
              </p>
              <div className="mt-3 pt-2 border-t border-slate-800 flex justify-center">
                <button
                  onClick={() => setDismissNavPrompt(true)}
                  className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1.5 transition cursor-pointer"
                >
                  <Hand className="w-3.5 h-3.5" />
                  <span>Dismiss & explore ocean map</span>
                </button>
              </div>
            </div>
          </div>
        )}

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

