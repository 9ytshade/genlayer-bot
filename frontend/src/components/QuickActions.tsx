'use client';

import React from 'react';
import { Send, Wallet, FileCode } from 'lucide-react';

interface QuickActionsProps {
  onSelectAction: (action: string) => void;
}

export default function QuickActions({ onSelectAction }: QuickActionsProps) {
  const actions = [
    { label: 'Check Balance', command: 'What is my balance?', icon: Wallet },
    { label: 'Send Tokens', command: 'Send 10 GEN to', icon: Send },
    { label: 'Deploy Contract', command: 'Create a contract for', icon: FileCode },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
      {actions.map((action) => {
        const Icon = action.icon;
        return (
          <button
            key={action.label}
            onClick={() => onSelectAction(action.command)}
            className="flex items-center gap-2 p-3 bg-bg-elevated border border-border-strong hover:border-accent-primary hover:bg-accent-primary/5 rounded text-left transition-all duration-200 group"
          >
            <Icon size={14} className="text-accent-primary flex-shrink-0 group-hover:scale-110 transition-transform" />
            <span className="text-[11px] font-mono uppercase tracking-widest font-bold text-text-primary group-hover:text-accent-primary">
              {action.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
