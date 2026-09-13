import React, { useState, useEffect, useRef } from 'react';
import { ArrowRight, Crosshair, Radio, Waves, Cpu, Shield, Zap, Activity, MapPinned, Database, ChevronDown } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useSurveyStore } from '../../store/useSurveyStore';

const bubbles = Array.from({ length: 28 }, (_, index) => index);
const particles = Array.from({ length: 38 }, (_, index) => index);

const STATS = [
  { label: 'Map-ready evidence', value: 'LIVE', unit: '', color: '#67D5DF', icon: MapPinned },
  { label: 'Missing navigation', value: 'NULL', unit: '', color: '#43B993', icon: Shield },
  { label: 'Onboard-ready runtime', value: 'EDGE', unit: '', color: '#9B8EFF', icon: Zap },
  { label: 'Traceable mission output', value: 'JSON', unit: '', color: '#FFB347', icon: Database },
];

const PILLARS = [
  { icon: Cpu,      title: 'Edge-First Runtime',        desc: 'YOLO26 integration ready for local sonar processing when a trained model is supplied.',        color: '#67D5DF' },
  { icon: Shield,   title: 'Navigation Refusal',        desc: 'A target without valid navigation remains unlocated—no fabricated latitude or longitude.',      color: '#43B993' },
  { icon: Activity, title: 'Evidence Traceability',     desc: 'Confidence, QC, calibration and source provenance stay with each reported detection.',           color: '#9B8EFF' },
  { icon: Database, title: 'Mission-Ready Output',      desc: 'Structured JSON, CSV, GeoJSON and PDF deliverables support review and hand-off.',               color: '#FFB347' },
];

const MISSION_TAGS = ['PS-26057', 'MoES / NIOT', 'Samudrayaan', 'Deep Ocean Mission', 'SIH 2026', 'Marine Debris AI', 'Ghost Gear Detection', 'Side-Scan Sonar', 'Jetson Orin Nano', 'YOLO26 Ready'];

/** Cinematic first-touch surface; operational controls stay inside the console. */
export const IntroLanding: React.FC = () => {
  const navigate = useNavigate();
  const { activeSurveyId } = useSurveyStore();
  const [isDiving, setIsDiving] = useState(false);
  const [isExploring, setIsExploring] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0.5, y: 0.5 });
  const [activeStatIdx, setActiveStatIdx] = useState(0);
  const heroRef = useRef<HTMLDivElement>(null);
  const mouseMoveRef = useRef<((e: MouseEvent) => void) | null>(null);
  const statTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const enterConsole = () => {
    if (isDiving || isExploring) return;
    // Stop non-essential animations immediately to free up compositor
    if (mouseMoveRef.current) window.removeEventListener('mousemove', mouseMoveRef.current);
    if (statTimerRef.current) clearInterval(statTimerRef.current);
    setIsDiving(true);
    // Navigate after the wipe bar finishes (650ms)
    window.setTimeout(() => navigate(`/surveys/${activeSurveyId}/console`), 680);
  };

  const exploreMissions = () => {
    if (isDiving || isExploring) return;
    setIsExploring(true);
    // Navigate after iris + fade (600ms)
    window.setTimeout(() => navigate('/ingest'), 640);
  };

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updatePreference = () => setReducedMotion(mediaQuery.matches);
    updatePreference();
    mediaQuery.addEventListener('change', updatePreference);
    return () => mediaQuery.removeEventListener('change', updatePreference);
  }, []);

  useEffect(() => {
    if (reducedMotion) return;
    const handleMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX / window.innerWidth, y: e.clientY / window.innerHeight });
    };
    mouseMoveRef.current = handleMove;
    window.addEventListener('mousemove', handleMove, { passive: true });
    return () => window.removeEventListener('mousemove', handleMove);
  }, [reducedMotion]);

  useEffect(() => {
    if (reducedMotion) {
      setActiveStatIdx(0);
      return;
    }
    const t = setInterval(() => setActiveStatIdx(i => (i + 1) % STATS.length), 2800);
    statTimerRef.current = t;
    return () => clearInterval(t);
  }, [reducedMotion]);

  const px = isDiving || isExploring ? 0 : (mousePos.x - 0.5) * 28;
  const py = isDiving || isExploring ? 0 : (mousePos.y - 0.5) * 16;

  const oceanClass = [
    'intro-ocean',
    isDiving    ? 'intro-ocean--diving'    : '',
    isExploring ? 'intro-ocean--exploring' : '',
  ].filter(Boolean).join(' ');

  return (
    <main className={oceanClass}>
      {/* Backgrounds */}
      <div className="intro-noise" aria-hidden="true" />
      <div className="intro-caustics" aria-hidden="true" />
      <div className="intro-scanline" aria-hidden="true" />
      <div className="intro-depth-glow intro-depth-glow--one" aria-hidden="true" />
      <div className="intro-depth-glow intro-depth-glow--two" aria-hidden="true" />
      <div className="intro-depth-glow intro-depth-glow--three" aria-hidden="true" />

      {/* Bubbles */}
      <div className="intro-bubbles" aria-hidden="true">
        {bubbles.map((bubble) => <span key={bubble} style={{ '--bubble': bubble } as React.CSSProperties} />)}
      </div>

      {/* Floating particles */}
      <div className="intro-particles" aria-hidden="true">
        {particles.map((p) => <span key={p} style={{ '--p': p } as React.CSSProperties} />)}
      </div>

      {/* Coral reefs */}
      <div className="intro-reef intro-reef--left" aria-hidden="true" />
      <div className="intro-reef intro-reef--right" aria-hidden="true" />

      {/* Sonar rings */}
      <div className="intro-sonar-rings" aria-hidden="true">
        <span /><span /><span /><span />
      </div>

      {/* Fish school */}
      <div className="intro-fish-school" aria-hidden="true">
        <span /><span /><span /><span /><span /><span />
      </div>

      {/* Parallax sonar grid */}
      <div
        className="intro-sonar-grid"
        aria-hidden="true"
        style={{ transform: `translate3d(${px * 0.2}px, ${py * 0.15}px, 0)` }}
      />

      {/* AUV with parallax */}
      <div
        className="intro-auv"
        aria-hidden="true"
        style={{ '--auv-px': `${px * 0.6}px`, '--auv-py': `${py * 0.4}px` } as React.CSSProperties}
      >
        <div className="intro-auv__beam" />
        <div className="intro-auv__body">
          <span className="intro-auv__window" />
          <span className="intro-auv__fin intro-auv__fin--top" />
          <span className="intro-auv__fin intro-auv__fin--bottom" />
          <span className="intro-auv__light" />
          <span className="intro-auv__propeller" />
        </div>
        <div className="intro-auv__trail" />
        <div className="intro-auv__sonar-pulse" />
        <div className="intro-auv__hud">
          <span>AUV LINK</span>
          <span>SONAR MODE</span>
        </div>
      </div>

      {/* NAV */}
      <header className="intro-nav">
        <div className="intro-brand">
          <span className="intro-brand__mark"><Waves /></span>
          <span>AQUA<span>SENSE</span></span>
        </div>
        <nav className="intro-nav__links">
          <button type="button" onClick={exploreMissions} className="intro-nav__link">Mission intake</button>
          <button type="button" onClick={enterConsole} className="intro-nav__link">Console</button>
        </nav>
        <div className="intro-nav__right">
          <div className="intro-nav__status"><Radio /> SONAR INTELLIGENCE</div>
          <span className="intro-nav__badge">v2.4.1</span>
        </div>
      </header>

      {/* Mission tag ribbon */}
      <div className="intro-tag-ribbon" aria-label="Mission metadata">
        <div className="intro-tag-ribbon__track">
          {[...MISSION_TAGS, ...MISSION_TAGS].map((tag, i) => (
            <span key={i} className="intro-tag-ribbon__item">{tag}</span>
          ))}
        </div>
      </div>

      {/* HERO */}
      <section className="intro-hero" ref={heroRef} id="features">
        <div className="intro-eyebrow"><span /> MoES / NIOT · DEEP OCEAN MISSION · PS-26057</div>
        <h1>See what the<br /><em>ocean</em> keeps.</h1>
        <p>AI-powered side-scan sonar intelligence for reviewing <strong>marine debris</strong>, <strong>ghost gear</strong>, and subsea hazards. Build an evidence trail from ping to map-ready report, with edge-first deployment when your trained model is ready.</p>

        {/* Live stat ticker */}
        <div className="intro-stat-ticker">
          {STATS.map((s, i) => (
            <div
              key={i}
              className={`intro-stat ${i === activeStatIdx ? 'intro-stat--active' : ''}`}
              style={{ '--stat-color': s.color } as React.CSSProperties}
            >
              <s.icon />
              <span className="intro-stat__value">{s.value}<em>{s.unit}</em></span>
              <span className="intro-stat__label">{s.label}</span>
            </div>
          ))}
        </div>

        <div className="intro-actions">
          <button
            className={`intro-enter ${isDiving ? 'intro-enter--diving' : ''}`}
            onClick={enterConsole}
            disabled={isDiving || isExploring}
          >
            <span>{isDiving ? 'DIVING…' : 'ENTER MISSION CONSOLE'}</span>
            <ArrowRight />
          </button>
          <button
            className={`intro-secondary ${isExploring ? 'intro-secondary--leaving' : ''}`}
            onClick={exploreMissions}
            disabled={isDiving || isExploring}
          >
            <Crosshair /> {isExploring ? 'LOADING…' : 'EXPLORE MISSIONS'}
          </button>
        </div>
      </section>

      {/* Feature pillars strip */}
      <section className="intro-pillars" id="tech">
        <div className="intro-pillars__grid">
          {PILLARS.map((p, i) => (
            <div key={i} className="intro-pillar" style={{ '--pillar-color': p.color } as React.CSSProperties}>
              <div className="intro-pillar__icon"><p.icon /></div>
              <div className="intro-pillar__text">
                <strong>{p.title}</strong>
                <span>{p.desc}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Scroll hint */}
      <div className="intro-scroll-hint" aria-hidden="true">
        <ChevronDown />
        <span>READY TO DIVE</span>
      </div>

      <footer className="intro-footer">
        <span>PS 26057 · MARINE DEBRIS &amp; ANOMALY DETECTION</span>
        <span className="intro-scroll">DIVE DEEPER <i /></span>
        <span>EDGE-FIRST · MAP-READY · JETSON ORIN NANO</span>
      </footer>

      {/* Console wipe: GPU-only vertical translate, no repaints */}
      <div className="intro-wipe" aria-hidden="true" />
      {/* Explore portal: simple iris-fade overlay */}
      <div className="intro-portal" aria-hidden="true" />
    </main>
  );
};
