import { create } from 'zustand';

export const useNodeStore = create((set, get) => ({
  nodeHealth: [],
  anomalies: [],

  setHealth: (payload) =>
    set({
      nodeHealth: payload?.nodes || [],
      anomalies: payload?.anomalies || [],
    }),

  setAnomaly: (anomaly) => {
    if (!anomaly?.alert_id) return;
    const next = get().anomalies.filter((a) => a.alert_id !== anomaly.alert_id);
    if (anomaly.status !== 'resolved') {
      set({ anomalies: [anomaly, ...next].slice(0, 20) });
    } else {
      set({ anomalies: next });
    }
  },

  clearAnomalies: () => set({ anomalies: [] }),
}));