'use client';

import React, { useState } from 'react';
import { Search, X, Command, History } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectCommand: (command: string) => void;
  recentCommands: string[];
}

const commonCommands = [
  { label: 'Check Balance', command: 'What is my balance?' },
  { label: 'Send Tokens', command: 'Send 10 GEN to' },
  { label: 'Conditional Payment', command: 'Pay 100 GEN to 0x if ETH reaches 10000' },
  { label: 'Escrow Service', command: 'Create escrow for 500 GEN between 0x and 0x' },
  { label: 'Subscription Payment', command: 'Send 50 GEN weekly to 0x' },
  { label: 'Bounty Management', command: 'Create 1000 GEN bounty for landing page' },
  { label: 'Deploy Contract', command: 'Deploy contract' },
  { label: 'Generate Contract', command: '/generate-contract ' },
  { label: 'Get Help', command: 'help' },
  { label: 'View History', command: 'Show my transaction history' },
];

export default function CommandPalette({ isOpen, onClose, onSelectCommand, recentCommands }: CommandPaletteProps) {
  const [search, setSearch] = useState('');

  const filteredCommands = commonCommands.filter(cmd =>
    cmd.label.toLowerCase().includes(search.toLowerCase()) ||
    cmd.command.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            className="surface-shell fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-[8px]"
          >
            <div className="border-b border-border-default bg-bg-elevated p-4">
              <div className="relative flex items-center">
                <Search size={14} className="absolute left-3 text-text-muted" />
                <input
                  autoFocus
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search commands..."
                  className="field-input w-full py-2 pl-10 pr-4 font-mono text-[11px] text-text-primary placeholder:text-text-muted"
                />
              </div>
            </div>

            <div className="max-h-[400px] overflow-y-auto">
              {recentCommands.length > 0 && !search && (
                <>
                  <div className="border-b border-border-subtle px-4 py-2">
                    <div className="flex items-center gap-2">
                      <History size={10} />
                      <span className="micro-label">Recent</span>
                    </div>
                  </div>
                  {recentCommands.slice(0, 3).map((cmd, idx) => (
                    <button
                      key={`recent-${idx}`}
                      onClick={() => {
                        onSelectCommand(cmd);
                        onClose();
                      }}
                      className="w-full border-b border-border-subtle px-4 py-2 text-left font-mono text-[11px] text-text-secondary transition-colors hover:bg-bg-elevated hover:text-text-primary"
                    >
                      {cmd}
                    </button>
                  ))}
                </>
              )}

              <div className="border-b border-border-subtle px-4 py-2">
                <div className="flex items-center gap-2">
                  <Command size={10} />
                  <span className="micro-label">Commands</span>
                </div>
              </div>
              {filteredCommands.length > 0 ? (
                filteredCommands.map((cmd) => (
                  <button
                    key={cmd.command}
                    onClick={() => {
                      onSelectCommand(cmd.command);
                      onClose();
                    }}
                    className="group w-full border-b border-border-subtle px-4 py-3 text-left transition-colors hover:bg-bg-elevated"
                  >
                    <div className="font-mono text-[11px] font-bold text-accent-primary transition-colors group-hover:text-white">
                      {cmd.label}
                    </div>
                    <div className="text-[10px] font-mono text-text-muted group-hover:text-text-secondary mt-1">
                      {cmd.command}
                    </div>
                  </button>
                ))
              ) : (
                <div className="px-4 py-6 text-center font-mono text-[11px] text-text-muted">
                  No commands found
                </div>
              )}
            </div>

            <button
              onClick={onClose}
              className="control-button absolute right-3 top-3 rounded-[6px] p-1"
            >
              <X size={14} className="text-text-muted hover:text-text-primary" />
            </button>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
