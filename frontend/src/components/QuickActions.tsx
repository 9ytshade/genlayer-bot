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
    <div className="flex flex-wrap gap-2 pb-1 pt-1 sm:gap-3">
      {actions.map((action) => {
        const Icon = action.icon;
        return (
          <button
            key={action.label}
            onClick={() => onSelectAction(action.command)}
            className="control-button group flex min-h-9 items-center gap-2 rounded-full px-3.5 py-2 text-left shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] sm:px-4"
          >
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-primary/12 text-accent-primary transition-transform group-hover:scale-105">
              <Icon size={13} />
            </span>
            <span className="font-mono text-[10px] font-bold text-text-primary group-hover:text-accent-primary sm:text-[11px]">
              {action.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
