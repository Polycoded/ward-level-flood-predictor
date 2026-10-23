import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { buildWorld, DEFAULTS, planBroadcast, TIMING, type BroadcastPlan, type SimWorld } from '../../lib/broadcastSim';
import type { SimulationRequest } from '../../lib/store';
import type { WardLite } from '../../types';
import { loadWardIndex } from '../resident/hooks';

/** Illustrative control-room position (central Chennai). */
const CONTROL_ROOM = { lat: 13.0836, lng: 80.2705 };
const PHONE_OPTIONS = [1500, 3000, 6000];

type ShowPath = 'both' | 'cell' | 'app';

const COLORS = {
  bg: '#f8fafc',
  wardLine: '#cbd5e1',
  targetFill: { warning: 'rgba(220,38,38,0.16)', watch: 'rgba(245,158,11,0.18)' },
  targetLine: { warning: '#b91c1c', watch: '#b45309' },
  tower: '#475569',
  towerOn: '#dc2626',
  ring: 'rgba(220,38,38,',
  link: 'rgba(30,64,175,0.55)',
  phone: '#94a3b8',
  phoneTarget: '#475569',
  cell: '#ea580c',
  app: '#2563eb',
  overshoot: '#ea580c',
  missed: '#111827',
};

interface LogLine {
  atMs: number;
  text: string;
}

function buildLog(plan: BroadcastPlan, title: string, show: ShowPath): LogLine[] {
  const { stats } = plan;
  const shown = plan.deliveries.filter((d) => show === 'both' || d.path === show);
  const lines: LogLine[] = [{ atMs: 0, text: `Alert approved: ${title}` }];
  if (show !== 'app' && plan.broadcastingTowers.length) {
    lines.push({ atMs: TIMING.towerStartMs, text: `${plan.broadcastingTowers.length} towers start cell broadcast` });
  }
  if (show !== 'cell') lines.push({ atMs: TIMING.appMinMs, text: 'Push + WhatsApp sent to subscribed phones in the area' });
  const inTarget = shown.filter((d) => d.inTargetWard);
  const firstIn = inTarget[0];
  if (firstIn) lines.push({ atMs: firstIn.atMs, text: 'First phone in the alert area receives the alert' });
  const seen = new Set<number>();
  for (const d of inTarget) {
    seen.add(d.phoneId);
    if (seen.size >= Math.ceil(stats.phonesInTargetWards * 0.9)) {
      lines.push({ atMs: d.atMs, text: '90% of phones in the alert area reached' });
      break;
    }
  }
  const lastMs = shown.reduce((m, d) => Math.max(m, d.atMs), 0);
  const reached = new Set(inTarget.map((d) => d.phoneId)).size;
  lines.push({ atMs: lastMs + 200, text: `Delivery complete: ${reached} of ${stats.phonesInTargetWards} phones in the area` });
  return lines.sort((a, b) => a.atMs - b.atMs);
}

/** Full-screen animation of an approved alert going out: control room → towers → phones. */
export function BroadcastSimulation({ request, onClose }: { request: SimulationRequest; onClose: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [wards, setWards] = useState<WardLite[] | null>(null);
  const [phoneCount, setPhoneCount] = useState<number>(DEFAULTS.phones);
  const [show, setShow] = useState<ShowPath>('both');
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState(false);
  const reducedMotion = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  useEffect(() => {
    loadWardIndex().then((index) => setWards(index.list())).catch(() => setError(true));
  }, []);

  const world: SimWorld | null = useMemo(() => (wards ? buildWorld(wards, { phones: phoneCount }) : null), [wards, phoneCount]);
  const plan: BroadcastPlan | null = useMemo(() => (world ? planBroadcast(world, request.wardIds) : null), [world, request.wardIds]);
  const log = useMemo(() => (plan ? buildLog(plan, request.title, show) : []), [plan, request.title, show]);
  const endMs = plan ? plan.stats.lastDeliveryMs + 1200 : 0;

  // --- playback -------------------------------------------------------------
  const start = useRef(0);
  const raf = useRef(0);
  const play = useCallback(() => {
    if (!plan) return;
    if (reducedMotion) {
      setT(endMs);
      return;
    }
    cancelAnimationFrame(raf.current);
    start.current = performance.now();
    setPlaying(true);
    const tick = (now: number) => {
      const elapsed = now - start.current;
      setT(Math.min(elapsed, endMs));
      if (elapsed < endMs) raf.current = requestAnimationFrame(tick);
      else setPlaying(false);
    };
    raf.current = requestAnimationFrame(tick);
  }, [plan, endMs, reducedMotion]);

  useEffect(() => {
    play();
    return () => cancelAnimationFrame(raf.current);
  }, [play]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  // --- drawing --------------------------------------------------------------
  const [size, setSize] = useState({ w: 800, h: 600 });
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      if (r.width && r.height) setSize({ w: r.width, h: r.height });
    };
    measure();
    // older Android web views lack ResizeObserver; window resizes are close enough there
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', measure);
      return () => window.removeEventListener('resize', measure);
    }
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const projection = useMemo(() => {
    if (!world) return null;
    const { minLat, maxLat, minLng, maxLng } = world.bounds;
    const cos = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180);
    const spanX = (maxLng - minLng) * cos;
    const spanY = maxLat - minLat;
    const pad = 16;
    const scale = Math.min((size.w - pad * 2) / spanX, (size.h - pad * 2) / spanY);
    const offX = (size.w - spanX * scale) / 2;
    const offY = (size.h - spanY * scale) / 2;
    const pxPerKm = scale / 111.32;
    return {
      x: (lng: number) => offX + (lng - minLng) * cos * scale,
      y: (lat: number) => offY + (maxLat - lat) * scale,
      pxPerKm,
    };
  }, [world, size]);

  const wardLayer = useMemo(() => {
    if (!wards || !projection || typeof document === 'undefined') return null;
    const dpr = window.devicePixelRatio || 1;
    const layer = document.createElement('canvas');
    layer.width = Math.max(1, Math.round(size.w * dpr));
    layer.height = Math.max(1, Math.round(size.h * dpr));
    const ctx = layer.getContext('2d');
    if (!ctx) return null;
    ctx.scale(dpr, dpr);
    const targets = new Set(request.wardIds);
    for (const w of wards) {
      const polys = w.geometry.type === 'Polygon' ? [w.geometry.coordinates] : w.geometry.coordinates;
      ctx.beginPath();
      for (const rings of polys) for (const ring of rings) {
        ring.forEach(([lng, lat], i) => (i ? ctx.lineTo(projection.x(lng), projection.y(lat)) : ctx.moveTo(projection.x(lng), projection.y(lat))));
        ctx.closePath();
      }
      const target = targets.has(w.ward_id);
      if (target) {
        ctx.fillStyle = COLORS.targetFill[request.level];
        ctx.fill('evenodd');
      }
      ctx.strokeStyle = target ? COLORS.targetLine[request.level] : COLORS.wardLine;
      ctx.lineWidth = target ? 1.5 : 0.6;
      ctx.stroke();
    }
    return layer;
  }, [wards, projection, size, request.wardIds, request.level]);

  // phone states at time t
  const deliveredAt = useMemo(() => {
    const cell = new Map<number, number>();
    const app = new Map<number, number>();
    for (const d of plan?.deliveries ?? []) (d.path === 'cell' ? cell : app).set(d.phoneId, d.atMs);
    return { cell, app };
  }, [plan]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !world || !plan || !projection) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(size.w * dpr);
    canvas.height = Math.round(size.h * dpr);
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, size.w, size.h);
    if (wardLayer) ctx.drawImage(wardLayer, 0, 0, size.w, size.h);

    const towerById = new Map(world.towers.map((tw) => [tw.id, tw]));
    const active = new Map(plan.broadcastingTowers.map((b) => [b.towerId, b.startMs]));
    const cx = projection.x(CONTROL_ROOM.lng);
    const cy = projection.y(CONTROL_ROOM.lat);

    // control room → tower links while the message travels
    if (show !== 'app') {
      for (const { towerId, startMs } of plan.broadcastingTowers) {
        const tw = towerById.get(towerId)!;
        const p = Math.min(1, t / startMs);
        if (t > startMs + 600) continue;
        ctx.strokeStyle = COLORS.link;
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(cx + (projection.x(tw.lng) - cx) * p, cy + (projection.y(tw.lat) - cy) * p);
        ctx.stroke();
        ctx.setLineDash([]);
      }
      // broadcast rings
      for (const { towerId, startMs } of plan.broadcastingTowers) {
        if (t < startMs) continue;
        const tw = towerById.get(towerId)!;
        const km = ((t - startMs) / 1000) * TIMING.ringKmPerSec;
        if (km > DEFAULTS.towerRangeKm * 1.15) continue;
        const alpha = Math.max(0, 0.55 * (1 - km / (DEFAULTS.towerRangeKm * 1.15)));
        ctx.strokeStyle = `${COLORS.ring}${alpha.toFixed(3)})`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(projection.x(tw.lng), projection.y(tw.lat), km * projection.pxPerKm, 0, Math.PI * 2);
        ctx.stroke();
      }
    }

    // towers
    for (const tw of world.towers) {
      const on = show !== 'app' && active.has(tw.id) && t >= active.get(tw.id)!;
      const x = projection.x(tw.lng);
      const y = projection.y(tw.lat);
      ctx.fillStyle = on ? COLORS.towerOn : COLORS.tower;
      ctx.beginPath();
      ctx.moveTo(x, y - (on ? 6 : 4));
      ctx.lineTo(x - (on ? 4.5 : 3), y + (on ? 4 : 3));
      ctx.lineTo(x + (on ? 4.5 : 3), y + (on ? 4 : 3));
      ctx.closePath();
      ctx.fill();
    }

    // phones
    const targets = new Set(plan.targetWardIds);
    const done = t >= endMs - 1;
    for (const p of world.phones) {
      const x = projection.x(p.lng);
      const y = projection.y(p.lat);
      const cellAt = show !== 'app' ? deliveredAt.cell.get(p.id) : undefined;
      const appAt = show !== 'cell' ? deliveredAt.app.get(p.id) : undefined;
      const gotCell = cellAt !== undefined && t >= cellAt;
      const gotApp = appAt !== undefined && t >= appAt;
      const inTarget = targets.has(p.wardId);
      if (gotCell && !inTarget) {
        ctx.strokeStyle = COLORS.overshoot;
        ctx.lineWidth = 1;
        ctx.strokeRect(x - 1.5, y - 1.5, 3, 3);
      } else if (gotCell || gotApp) {
        ctx.fillStyle = gotCell ? COLORS.cell : COLORS.app;
        ctx.fillRect(x - 2, y - 2, 4, 4);
        if (gotCell && gotApp) {
          ctx.strokeStyle = COLORS.app;
          ctx.lineWidth = 1;
          ctx.strokeRect(x - 3, y - 3, 6, 6);
        }
      } else if (inTarget && done) {
        ctx.strokeStyle = COLORS.missed; // never reached
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(x - 2.5, y - 2.5); ctx.lineTo(x + 2.5, y + 2.5);
        ctx.moveTo(x + 2.5, y - 2.5); ctx.lineTo(x - 2.5, y + 2.5);
        ctx.stroke();
      } else {
        ctx.fillStyle = inTarget ? COLORS.phoneTarget : COLORS.phone;
        ctx.fillRect(x - 1, y - 1, 2, 2);
      }
    }

    // control room
    const pulse = t < TIMING.towerStartMs ? 1 + 0.4 * Math.sin(t / 80) : 1;
    ctx.fillStyle = '#1e3a8a';
    ctx.beginPath();
    ctx.arc(cx, cy, 7 * pulse, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 9px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('HQ', cx, cy);
  }, [t, world, plan, projection, wardLayer, size, show, deliveredAt, endMs]);

  // --- live counters ----------------------------------------------------------
  const counts = useMemo(() => {
    if (!plan) return null;
    const upTo = plan.deliveries.filter((d) => d.atMs <= t && (show === 'both' || d.path === show));
    const inTargetReached = new Set(upTo.filter((d) => d.inTargetWard).map((d) => d.phoneId)).size;
    return {
      inTargetReached,
      cell: upTo.filter((d) => d.path === 'cell' && d.inTargetWard).length,
      app: upTo.filter((d) => d.path === 'app').length,
      overshoot: upTo.filter((d) => d.path === 'cell' && !d.inTargetWard).length,
    };
  }, [plan, t, show]);

  const s = plan?.stats;
  const pct = (n: number) => (s && s.phonesInTargetWards ? Math.round((n / s.phonesInTargetWards) * 100) : 0);

  return createPortal(
    <div role="dialog" aria-modal="true" aria-label="Alert delivery simulation" className="fixed inset-0 z-[70] bg-white flex flex-col">
      <header className="flex items-start gap-3 px-4 py-3 border-b border-gray-200">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h2 className="text-lg font-semibold text-gray-900">Alert delivery simulation</h2>
            <span className="text-[11px] font-bold uppercase tracking-wide bg-gray-900 text-white rounded px-2 py-0.5">
              Simulation: synthetic towers &amp; phones
            </span>
          </div>
          <p className="text-xs text-gray-700 truncate mt-0.5">{request.title}</p>
        </div>
        <button onClick={onClose} className="btn-secondary shrink-0" aria-label="Close simulation">Close</button>
      </header>

      <div className="flex-1 min-h-0 flex flex-col lg:flex-row">
        <div ref={wrapRef} className="relative flex-1 min-h-[320px]">
          <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" aria-label="Map of towers and phones receiving the alert" role="img" />
          {!world && !error && <p role="status" className="absolute inset-0 flex items-center justify-center text-gray-700">Placing towers and phones…</p>}
          {error && <p role="alert" className="absolute inset-0 flex items-center justify-center text-red-800">Could not load ward shapes.</p>}
          <div className="absolute left-0 right-0 bottom-0 h-1.5 bg-gray-200" aria-hidden="true">
            <div className="h-full bg-flood-700" style={{ width: `${endMs ? (t / endMs) * 100 : 0}%` }} />
          </div>
        </div>

        <aside className="w-full lg:w-80 border-t lg:border-t-0 lg:border-l border-gray-200 p-4 space-y-4 overflow-y-auto">
          <div className="flex flex-wrap gap-2">
            <button onClick={play} disabled={!plan || playing} className="btn-primary">{playing ? 'Playing…' : '▶ Replay'}</button>
            <label className="text-sm text-gray-800 flex items-center gap-1">
              Phones
              <select value={phoneCount} onChange={(e) => setPhoneCount(Number(e.target.value))} className="input py-1 w-24">
                {PHONE_OPTIONS.map((n) => <option key={n} value={n}>{n.toLocaleString()}</option>)}
              </select>
            </label>
          </div>

          <div role="group" aria-label="Delivery path" className="grid grid-cols-3 gap-1 text-xs">
            {(['both', 'cell', 'app'] as ShowPath[]).map((p) => (
              <button
                key={p}
                onClick={() => setShow(p)}
                aria-pressed={show === p}
                className={`px-2 py-1.5 rounded border font-medium ${show === p ? 'bg-flood-700 text-white border-flood-700' : 'bg-white text-gray-800 border-gray-300'}`}
              >
                {p === 'both' ? 'Both' : p === 'cell' ? 'Cell broadcast' : 'App + WhatsApp'}
              </button>
            ))}
          </div>

          {s && counts && (
            <dl className="grid grid-cols-2 gap-2 text-sm" aria-live="polite">
              <div className="col-span-2 rounded-lg bg-gray-50 p-3">
                <dt className="text-xs text-gray-700">Phones in alert area reached</dt>
                <dd className="text-2xl font-bold text-gray-900 font-mono">
                  {counts.inTargetReached.toLocaleString()} <span className="text-base font-normal text-gray-700">/ {s.phonesInTargetWards.toLocaleString()} ({pct(counts.inTargetReached)}%)</span>
                </dd>
              </div>
              <div className="rounded-lg bg-orange-50 p-2.5">
                <dt className="text-xs text-orange-900">Cell broadcast</dt>
                <dd className="font-mono font-semibold text-orange-950">{counts.cell.toLocaleString()}</dd>
              </div>
              <div className="rounded-lg bg-blue-50 p-2.5">
                <dt className="text-xs text-blue-900">App + WhatsApp</dt>
                <dd className="font-mono font-semibold text-blue-950">{counts.app.toLocaleString()}</dd>
              </div>
              <div className="rounded-lg bg-gray-50 p-2.5">
                <dt className="text-xs text-gray-700">Also alerted outside the area</dt>
                <dd className="font-mono font-semibold text-gray-900">{counts.overshoot.toLocaleString()}</dd>
              </div>
              <div className="rounded-lg bg-gray-50 p-2.5">
                <dt className="text-xs text-gray-700">Towers broadcasting</dt>
                <dd className="font-mono font-semibold text-gray-900">{show === 'app' ? 0 : plan!.broadcastingTowers.length} / {world!.towers.length}</dd>
              </div>
            </dl>
          )}

          <section aria-labelledby="sim-log-title">
            <h3 id="sim-log-title" className="text-sm font-semibold text-gray-900 mb-1">Timeline</h3>
            <ol className="text-xs text-gray-800 space-y-1 font-mono">
              {log.filter((l) => l.atMs <= t).map((l, i) => (
                <li key={i}>T+{(l.atMs / 1000).toFixed(1)}s · <span className="font-sans">{l.text}</span></li>
              ))}
            </ol>
          </section>

          <section className="text-xs text-gray-800 space-y-1" aria-label="Legend">
            <p><span className="inline-block w-2.5 h-2.5 align-middle mr-1.5" style={{ background: COLORS.cell }} />Reached by cell broadcast</p>
            <p><span className="inline-block w-2.5 h-2.5 align-middle mr-1.5" style={{ background: COLORS.app }} />Reached by app push / WhatsApp only</p>
            <p><span className="inline-block w-2.5 h-2.5 align-middle mr-1.5 border" style={{ borderColor: COLORS.overshoot }} />Outside the area but under a broadcasting tower</p>
            <p><span className="inline-block w-2.5 align-middle mr-1.5 font-bold">✕</span>In the area, not reached (no signal, no app)</p>
            <p><span className="inline-block align-middle mr-1.5" style={{ color: COLORS.towerOn }}>▲</span>Tower broadcasting · <span style={{ color: COLORS.tower }}>▲</span> idle</p>
          </section>

          <p className="text-xs text-gray-600">
            Towers on a {DEFAULTS.towerSpacingKm} km grid; phones placed at random inside real ward boundaries; {Math.round(DEFAULTS.pushShare * 100)}% with the app, {Math.round(DEFAULTS.whatsappShare * 100)}% on WhatsApp, {Math.round(DEFAULTS.noSignalShare * 100)}% without signal. Illustrative timings, not measured network latency.
          </p>
        </aside>
      </div>
    </div>,
    document.body
  );
}
