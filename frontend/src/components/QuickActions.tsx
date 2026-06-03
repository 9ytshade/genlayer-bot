'use client';

import React from 'react';
import { Send, Wallet, FileCode, Sparkles } from 'lucide-react';

interface QuickActionsProps {
  onSelectAction: (action: string) => void;
}

export default function QuickActions({ onSelectAction }: QuickActionsProps) {
  const actions = [
    { label: 'Check Balance', command: 'What is my balance?', icon: Wallet },
    { label: 'Send Tokens', command: 'Send 10 GEN to', icon: Send },
    { label: 'Generate Contract', command: '/generate-contract ', icon: Sparkles },
    { label: 'Deploy Contract', command: 'Deploy contract', icon: FileCode },
  ];

  return (
    <div className="flex flex-wrap gap-4 px-2 pb-1 pt-1">
      {actions.map((action) => {
        const Icon = action.icon;
        return (
          <button
            key={action.label}
            onClick={() => onSelectAction(action.command)}
            className="control-button group flex min-h-12 items-center gap-3 rounded-full px-6 py-3.5 text-left shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
          >
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-primary/12 text-accent-primary transition-transform group-hover:scale-105">
              <Icon size={15} />
            </span>
            <span className="font-mono text-[11px] font-bold uppercase tracking-[0.08em] text-text-primary group-hover:text-accent-primary">
              {action.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
