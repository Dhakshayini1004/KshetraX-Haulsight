import MineMap from '../map/MineMap';
import VehicleList from '../panels/VehicleList';
import AlertPanel from '../panels/AlertPanel';
import SystemHealth from '../panels/SystemHealth';
import { RadarAIPanel, ProductionPanel, NodeHealthPanel } from '../ai/AIPanels';

export default function MainLayout() {
  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Map (primary hero, 58%) */}
      <div className="w-[58%] p-3 flex flex-col gap-3 min-w-0">
        <div className="flex-1 panel overflow-hidden">
          <div className="h-full">
            <MineMap />
          </div>
        </div>
        <SystemHealth />
      </div>

      {/* Right rail (secondary/tertiary, 42%) */}
      <div className="w-[42%] p-3 pl-0 flex flex-col gap-3 min-w-0 min-h-0 overflow-hidden">
        <div className="flex-[3] min-h-0">
          <VehicleList />
        </div>
        <div className="flex-[1.5] min-h-0">
          <AlertPanel />
        </div>
        <div className="flex-[2] min-h-0">
          <RadarAIPanel />
        </div>
        <div className="flex-[2] min-h-0">
          <ProductionPanel />
        </div>
        <div className="flex-[3.5] min-h-0">
          <NodeHealthPanel />
        </div>
      </div>
    </div>
  );
}
