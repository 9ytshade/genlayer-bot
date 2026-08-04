import React from 'react';
import { MessageSquare, Trash2, Plus } from 'lucide-react';
import GenLayerLogo from './GenLayerLogo';
import ConnectWalletButton from './ConnectWalletButton';
import { NETWORK_CONFIG, type NetworkKey } from '@/config';
import { MessageData } from '../lib/api';

export interface ChatSession {
  id: string;
  title: string;
  updatedAt: number;
  messages: MessageData[];
}

interface ChatSidebarProps {
  chats: ChatSession[];
  currentChatId: string;
  connectedWallet: string | null;
  selectedNetwork: NetworkKey;
  isLoading: boolean;
  onSelectChat: (id: string) => void;
  onDeleteChat: (id: string) => void;
  onCreateNewChat: () => void;
  onSetActivePanel: (panel: 'history' | 'chat' | 'logs') => void;
}

export default function ChatSidebar({
  chats,
  currentChatId,
  connectedWallet,
  selectedNetwork,
  isLoading,
  onSelectChat,
  onDeleteChat,
  onCreateNewChat,
  onSetActivePanel,
}: ChatSidebarProps) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 border-b border-border-default px-4 py-4 sm:px-5">
        <div className="mb-4 flex items-center justify-center rounded-[10px] border border-border-subtle bg-bg-base/60 p-3 text-center">
          <div className="min-w-0">
            <GenLayerLogo className="mx-auto h-5 w-32 text-text-primary" />
            <div className="micro-label mt-1 text-center">Wallet-scoped workspace</div>
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            onCreateNewChat();
            onSetActivePanel('chat');
          }}
          disabled={!connectedWallet || isLoading}
          className="primary-action flex h-10 w-full items-center justify-center gap-2 rounded-[8px] px-4 font-mono text-[11px] font-bold"
          title="Start new chat"
        >
          <Plus size={13} />
          New Chat
        </button>
      </div>

      <div className="shrink-0 border-b border-border-default px-4 py-4 sm:px-5">
        <div className="mb-2 flex items-center justify-between">
          <span className="micro-label">Connected</span>
          <span className={`h-2 w-2 rounded-full ${connectedWallet ? 'bg-accent-success' : 'bg-accent-danger'}`} />
        </div>
        <div className="rounded-[10px] border border-border-subtle bg-bg-base/55 p-3">
          <div className="truncate font-mono text-[11px] font-semibold text-text-primary">
            {connectedWallet ? `${connectedWallet.slice(0, 6)}...${connectedWallet.slice(-4)}` : 'No wallet'}
          </div>
          <div className="mt-1 font-mono text-[9px] uppercase tracking-[0.08em] text-text-muted">
            {connectedWallet ? `${NETWORK_CONFIG[selectedNetwork].label} - sync active` : 'Connect to load chats'}
          </div>
          <div className="mt-3">
            <ConnectWalletButton network={selectedNetwork} />
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-5">
        <div className="micro-label mb-3">Chats</div>
        {connectedWallet ? (
          <div className="space-y-2">
            {chats.map((chat) => (
              <div
                key={chat.id}
                className={`group flex items-start gap-2 rounded-[10px] border p-3 transition-colors ${
                  chat.id === currentChatId
                    ? 'border-accent-primary/55 bg-accent-primary/10 text-text-primary'
                    : 'border-border-subtle bg-bg-base/35 text-text-secondary hover:border-border-strong hover:bg-bg-base'
                }`}
              >
                <button
                  type="button"
                  onClick={() => {
                    onSelectChat(chat.id);
                    onSetActivePanel('chat');
                  }}
                  className="min-w-0 flex-1 text-left"
                  title={chat.title}
                >
                  <div className="flex items-center gap-2">
                  <MessageSquare size={13} className="shrink-0 text-text-muted group-hover:text-accent-primary" />
                  <span className="min-w-0 flex-1 truncate font-mono text-[11px] font-semibold">
                    {chat.title}
                  </span>
                  </div>
                  <div className="mt-1 truncate pl-5 font-mono text-[9px] uppercase tracking-[0.06em] text-text-muted">
                  {chat.messages.length} messages - today
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => onDeleteChat(chat.id)}
                  className="control-button flex h-7 w-7 shrink-0 items-center justify-center rounded-[7px] opacity-70 transition-opacity hover:opacity-100"
                  title="Delete chat"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-[10px] border border-border-subtle bg-bg-base/35 p-3 text-[11px] leading-relaxed text-text-muted">
            Connect a wallet to load synced chats, sign SIWE, and deploy.
          </div>
        )}
      </div>
    </div>
  );
}
