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
  { label: 'Deploy Contract', command: 'Create a contract for' },
  { label: 'Get Help', command: 'Help' },
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
            className="fixed inset-0 bg-black/50 z-40"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-full max-w-md z-50 bg-bg-surface border border-border-strong rounded-lg overflow-hidden"
          >
            <div className="p-4 border-b border-border-strong bg-bg-elevated">
              <div className="relative flex items-center">
                <Search size={14} className="absolute left-3 text-text-muted" />
                <input
                  autoFocus
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search commands..."
                  className="w-full bg-bg-base border border-border-strong pl-10 pr-4 py-2 text-[11px] font-mono text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary"
                />
              </div>
            </div>

            <div className="max-h-[400px] overflow-y-auto">
              {recentCommands.length > 0 && !search && (
                <>
                  <div className="px-4 py-2 text-[10px] font-mono uppercase tracking-widest text-text-muted border-b border-border-subtle">
                    <div className="flex items-center gap-2">
                      <History size={10} />
                      Recent
                    </div>
                  </div>
                  {recentCommands.slice(0, 3).map((cmd, idx) => (
                    <button
                      key={`recent-${idx}`}
                      onClick={() => {
                        onSelectCommand(cmd);
                        onClose();
                      }}
                      className="w-full text-left px-4 py-2 hover:bg-bg-elevated transition-colors text-[11px] font-mono text-text-secondary hover:text-text-primary border-b border-border-subtle"
                    >
                      {cmd}
                    </button>
                  ))}
                </>
              )}

              <div className="px-4 py-2 text-[10px] font-mono uppercase tracking-widest text-text-muted border-b border-border-subtle">
                <div className="flex items-center gap-2">
                  <Command size={10} />
                  Commands
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
                    className="w-full text-left px-4 py-3 hover:bg-bg-elevated transition-colors border-b border-border-subtle group"
                  >
                    <div className="text-[11px] font-mono font-bold text-accent-primary group-hover:text-white transition-colors">
                      {cmd.label}
                    </div>
                    <div className="text-[10px] font-mono text-text-muted group-hover:text-text-secondary mt-1">
                      {cmd.command}
                    </div>
                  </button>
                ))
              ) : (
                <div className="px-4 py-6 text-center text-text-muted text-[11px] font-mono">
                  No commands found
                </div>
              )}
            </div>

            <button
              onClick={onClose}
              className="absolute top-3 right-3 p-1 hover:bg-border-strong rounded transition-colors"
            >
              <X size={14} className="text-text-muted hover:text-text-primary" />
            </button>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
