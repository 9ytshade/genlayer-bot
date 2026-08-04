import React from 'react';
import { History, Activity } from 'lucide-react';
import { NETWORK_CONFIG, type NetworkKey } from '@/config';
import ConnectWalletButton from './ConnectWalletButton';
import QuickActions from './QuickActions';

interface ChatHeaderProps {
  selectedNetwork: NetworkKey;
  connectedWallet: string | null;
  handleNetworkChange: (network: NetworkKey) => void;
  setActivePanel: (panel: 'history' | 'chat' | 'logs') => void;
  handleQuickAction: (action: string) => void;
}

export default function ChatHeader({
  selectedNetwork,
  connectedWallet,
  handleNetworkChange,
  setActivePanel,
  handleQuickAction,
}: ChatHeaderProps) {
  return (
    <div className="shrink-0 border-b border-border-default bg-bg-base/80 px-4 py-3 backdrop-blur sm:px-6 sm:py-4 xl:px-8">
      <div className="mb-3 flex min-h-9 items-start justify-between gap-3 lg:justify-start">
        <button
          type="button"
          onClick={() => setActivePanel('history')}
          className="control-button flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] lg:hidden"
          title="Open chat history"
        >
          <History size={13} />
        </button>

        <div className="min-w-0 flex-1">
          <div className="micro-label mb-1">Intelligent Contract Workbench</div>
          <h1 className="truncate font-display text-[17px] font-semibold leading-tight text-text-primary sm:text-[20px]">
            GenLayer Chatbot
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="status-pill border-accent-success/45 bg-accent-success/5 text-accent-success">
              {NETWORK_CONFIG[selectedNetwork].label}
            </span>
            {connectedWallet && (
              <span className="status-pill text-text-secondary">
                {connectedWallet.slice(0, 6)}...{connectedWallet.slice(-4)}
              </span>
            )}
          </div>
        </div>

        <div className="hidden shrink-0 items-center gap-2 lg:flex">
          <label htmlFor="network-select" className="micro-label">
            Network
          </label>
          <select
            id="network-select"
            value={selectedNetwork}
            onChange={(e) => {
              handleNetworkChange(e.target.value as NetworkKey);
            }}
            className="field-input rounded-full px-3 py-2 font-mono text-[10px] text-text-secondary"
          >
            {Object.entries(NETWORK_CONFIG).map(([key, cfg]) => (
              <option key={key} value={key}>
                {cfg.label}
              </option>
            ))}
          </select>
          <ConnectWalletButton network={selectedNetwork} />
        </div>

        <button
          type="button"
          onClick={() => setActivePanel('logs')}
          className="control-button flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] lg:hidden"
          title="Open activity logs"
        >
          <Activity size={13} />
        </button>
      </div>

      <QuickActions onSelectAction={handleQuickAction} />
    </div>
  );
}
