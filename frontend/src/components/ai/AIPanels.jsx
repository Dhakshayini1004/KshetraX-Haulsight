import { Radio, TrendingUp, Gauge } from 'lucide-react';
import { useAIStore } from '../../stores/aiStore';
import { useNodeStore } from '../../stores/nodeStore';

const CLASS_DOT = {
  VEHICLE: 'bg-safe',
  ANIMAL: 'bg-warning',
  ROCK: 'bg-orange',
  UNKNOWN: 'bg-brown/40',
};

const NODE_STATUS = {
  NORMAL: { dot: 'bg-healthy', text: 'text-safe', chip: 'bg-healthy/10 text-safe' },
  WARNING: { dot: 'bg-warning', text: 'text-warning', chip: 'bg-warning/10 text-warning' },
  CRITICAL: { dot: 'bg-critical', text: 'text-critical', chip: 'bg-critical/10 text-critical' },
};

export function RadarAIPanel() {
  const classifications = useAIStore((s) => s.radarClassifications);
  const latest = classifications[0];

  const details = [
    { label: 'Range', value: latest?.features?.range_m != null ? `${latest.features.range_m.toFixed(0)} m` : '—' },
    { label: 'Relative speed', value: latest?.features?.relative_speed_mps != null ? `${latest.features.relative_speed_mps.toFixed(1)} m/s` : '—' },
    { label: 'Size', value: latest?.features?.size != null ? `${latest.features.size.toFixed(1)} m` : '—' },
  ];

  return (
    <div className="panel overflow-hidden">
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <Radio size={15} className="text-brown/50" strokeWidth={1.75} />
          <h2 className="panel-title">Radar Classification</h2>
        </div>
        <span className="text-[10px] uppercase tracking-wide text-brown/35">Model · Classifier v1</span>
      </div>

      <div className="panel-body">
        {!latest ? (
          <div className="text-[12px] text-brown/40">Waiting for radar detections…</div>
        ) : (
          <>
            <div className="flex items-center gap-2.5">
              <span className={`w-2.5 h-2.5 rounded-full ${CLASS_DOT[latest.object_class] || 'bg-brown/40'}`} />
              <span className="text-lg font-bold text-brown">{latest.object_class}</span>
              <span className="text-[12px] text-brown/45">{latest.confidence}% confidence</span>
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2 border-t border-cream-dark/60 pt-3">
              {details.map((d) => (
                <div key={d.label} className="leading-tight">
                  <div className="text-[10px] text-brown/40 uppercase tracking-wide">{d.label}</div>
                  <div className="text-[13px] font-semibold text-brown">{d.value}</div>
                </div>
              ))}
            </div>

            {latest.is_false_positive && (
              <div className="mt-2 text-[11px] text-brown/55">
                Non-vehicle detection — no collision alert raised.
              </div>
            )}
          </>
        )}
      </div>
      <div className="px-4 pb-3 text-[10px] text-brown/35">Simulation data · {latest?.data_mode || 'SIMULATION'}</div>
    </div>
  );
}

export function NodeHealthPanel() {
  const nodeHealth = useNodeStore((s) => s.nodeHealth);
  const anomalies = useNodeStore((s) => s.anomalies);

  const abnormal = nodeHealth.filter((n) => n.status !== 'NORMAL');
  const activeCount = anomalies.filter((a) => a.status === 'active').length;

  return (
    <div className="panel panel-col overflow-hidden">
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <Gauge size={15} className="text-brown/50" strokeWidth={1.75} />
          <h2 className="panel-title">Node Health</h2>
          {activeCount > 0 && (
            <span className="text-[12px] font-bold text-warning leading-none">{activeCount}</span>
          )}
        </div>
        <span className="text-[10px] uppercase tracking-wide text-brown/35">Monitor</span>
      </div>

      <div className="panel-scrollable-body">
        {nodeHealth.length === 0 ? (
          <div className="text-[12px] text-brown/40">Waiting for node telemetry…</div>
        ) : (
          <>
            {activeCount > 0 && (
              <div className="mb-3 flex items-start gap-2 rounded-md bg-critical/10 px-3 py-2">
                <span className="w-2 h-2 mt-1 shrink-0 rounded-full bg-critical animate-pulse" />
                <div className="text-[12px] leading-snug text-brown">
                  <span className="font-semibold text-critical">
                    {anomalies[0]?.status} node anomaly
                  </span>
                  <div className="text-brown/70">
                    {anomalies[0]?.name} — {anomalies[0]?.location} · {anomalies[0]?.value}{anomalies[0]?.unit} (normal{' '}
                    {anomalies[0]?.normal_range?.min}–{anomalies[0]?.normal_range?.max}{anomalies[0]?.unit})
                  </div>
                </div>
              </div>
            )}

            <div className="flex flex-col divide-y divide-cream-dark/50">
              {nodeHealth.map((node) => {
                const st = NODE_STATUS[node.status] || NODE_STATUS.NORMAL;
                return (
                  <div key={node.node_id} className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`w-2 h-2 shrink-0 rounded-full ${st.dot}`} />
                      <div className="leading-tight min-w-0">
                        <div className={`text-[13px] font-semibold truncate ${st.text}`}>
                          {node.location}
                        </div>
                        <div className="text-[10px] text-brown/40">
                          {node.node_id} · {node.parameter.replace('_', ' ')}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[13px] font-semibold text-brown">
                        {node.value}<span className="text-[10px] text-brown/40">{node.unit}</span>
                      </span>
                      <span className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${st.chip}`}>
                        {node.status}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-1 text-[10px] text-brown/35">
              {abnormal.length > 0
                ? `${abnormal.length} node(s) outside normal range`
                : `${nodeHealth.length} critical nodes nominal`}
              {' · simulated sensor telemetry'}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function ProductionPanel() {
  const production = useAIStore((s) => s.production);
  const increase = production.increase_pct || 0;
  const impact = production.production_impact_pct || 0;
  const ready = production.normal_cycle_min > 0;

  return (
    <div className="panel overflow-hidden">
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <TrendingUp size={15} className="text-brown/50" strokeWidth={1.75} />
          <h2 className="panel-title">Production Forecast</h2>
        </div>
      </div>

      <div className="panel-body">
        {!ready ? (
          <div className="text-[12px] text-brown/40">Forecast pending…</div>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-2">
              <div className="leading-tight">
                <div className="text-[10px] text-brown/40 uppercase tracking-wide">Normal cycle</div>
                <div className="text-lg font-bold text-brown">
                  {Math.round(production.normal_cycle_min)}<span className="text-[11px] font-medium text-brown/50"> min</span>
                </div>
              </div>
              <div className="leading-tight">
                <div className="text-[10px] text-brown/40 uppercase tracking-wide">Predicted</div>
                <div className={`text-lg font-bold ${increase > 5 ? 'text-warning' : 'text-brown'}`}>
                  {Math.round(production.predicted_cycle_min)}<span className="text-[11px] font-medium text-brown/50"> min</span>
                </div>
              </div>
              <div className="leading-tight">
                <div className="text-[10px] text-brown/40 uppercase tracking-wide">Impact</div>
                <div className={`text-lg font-bold ${impact < 0 ? 'text-warning' : 'text-safe'}`}>{impact}%</div>
              </div>
            </div>

            <div className="mt-3 flex items-center justify-between border-t border-cream-dark/60 pt-2">
              <span className="text-[11px] text-brown/55">Haul-cycle {increase > 0 ? '+' : ''}{increase}%</span>
              <span className="text-[11px] text-brown/55">est. {production.confidence || 0}% confidence</span>
            </div>
            <div className="mt-1 text-[10px] text-brown/35">Simulation estimate · not actual mine production</div>
          </>
        )}
      </div>
    </div>
  );
}
