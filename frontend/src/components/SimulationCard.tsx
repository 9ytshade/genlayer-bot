import React from 'react';
import { SimulationResult } from '../lib/api';
import { Activity, AlertTriangle } from 'lucide-react';

export default function SimulationCard({ simulation }: { simulation: SimulationResult }) {
  return (
    <div className="mt-2 p-4 bg-black text-text-primary ticket-border font-mono text-[11px] uppercase tracking-wider">
      <div className={`flex items-center gap-2 mb-3 border-b border-border-strong pb-2 ${simulation.success ? 'text-accent-success' : 'text-accent-danger'}`}>
        <Activity size={14} />
        <span className="font-bold">SIMULATION_RESULT</span>
      </div>
      
      <div className="flex flex-col gap-2">
        <div className="flex justify-between border-b border-border-subtle border-dotted pb-1">
          <span className="text-text-muted">STATUS:</span>
          <span className={simulation.success ? 'text-accent-success font-bold' : 'text-accent-danger font-bold'}>
            {simulation.success ? 'SUCCESS' : 'FAILED'}
          </span>
        </div>
        
        <div className="flex justify-between border-b border-border-subtle border-dotted pb-1">
          <span className="text-text-muted">GAS_ESTIMATE:</span>
          <span className="text-accent-primary font-bold">{simulation.gasEstimate} WEI</span>
        </div>

        {simulation.summary && (
          <div className="mt-2 pt-2 border-t border-border-strong">
            <p className="text-text-secondary leading-relaxed normal-case tracking-normal">{simulation.summary}</p>
          </div>
        )}

        {simulation.cases && simulation.cases.length > 0 && (
          <div className="mt-2">
            <span className="text-text-muted">OUTCOMES:</span>
            <ul className="mt-1 space-y-1">
              {simulation.cases.map((c, i) => (
                <li key={i} className="flex items-start gap-2 text-text-secondary normal-case tracking-normal">
                  <div className="mt-0.5">
                    <AlertTriangle size={12} className="text-accent-primary" />
                  </div>
                  <span>{c}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
