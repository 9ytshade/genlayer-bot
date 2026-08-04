import React from 'react';
import { Command, FileUp, Loader2, SendHorizontal } from 'lucide-react';
import { NETWORK_CONFIG, type NetworkKey } from '@/config';
import { MessageData } from '../lib/api';

interface ChatInputProps {
  input: string;
  setInput: (value: string) => void;
  handleSubmit: (e: React.FormEvent) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  connectedWallet: string | null;
  isLoading: boolean;
  isNetworkMismatch: boolean;
  selectedNetwork: NetworkKey;
  messages: MessageData[];
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  handleFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  uploadError: string | null;
}

export default function ChatInput({
  input,
  setInput,
  handleSubmit,
  setCommandPaletteOpen,
  connectedWallet,
  isLoading,
  isNetworkMismatch,
  selectedNetwork,
  messages,
  fileInputRef,
  handleFileUpload,
  uploadError,
}: ChatInputProps) {
  const isInputDisabled = !connectedWallet || isLoading || messages.some((m) => m.status === 'awaiting_confirmation' || m.status === 'executing');
  const isSubmitDisabled = !connectedWallet || !input.trim() || isLoading || isNetworkMismatch || messages.some((m) => m.status === 'awaiting_confirmation' || m.status === 'executing');

  return (
    <div className="shrink-0 border-t border-border-default bg-bg-base/95 px-3 pb-16 pt-3 sm:px-5 lg:px-6 lg:pb-3">
      <form onSubmit={handleSubmit} className="panel-soft relative mx-auto flex w-full items-center gap-1.5 rounded-[12px] p-1.5 shadow-[0_18px_50px_rgba(0,0,0,0.24)] sm:gap-2">
        <button
          type="button"
          onClick={() => setCommandPaletteOpen(true)}
          disabled={!connectedWallet}
          className="control-button hidden h-9 w-9 items-center justify-center rounded-[9px] bg-accent-cyan/8 text-accent-cyan sm:flex"
          title={connectedWallet ? "Open command palette (Cmd+K)" : "Connect wallet first"}
        >
          <Command size={14} />
        </button>

        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileUpload}
          accept=".py"
          aria-label="Upload Python contract file"
          className="hidden"
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={!connectedWallet || isLoading}
          className="control-button flex h-9 w-9 items-center justify-center rounded-[9px] bg-accent-primary/8 text-accent-primary"
          title="Upload Intelligent Contract (.py)"
        >
          <FileUp size={14} />
        </button>

        <input
          type="text"
          aria-label="Chat message"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
              e.preventDefault();
              setCommandPaletteOpen(true);
            }
          }}
          placeholder={connectedWallet ? "Ask GenLayer Bot to check balance, send GEN, generate, validate, or deploy a contract..." : "Connect wallet to chat..."}
          className="min-h-9 flex-1 border-none bg-transparent px-2 font-mono text-[11px] text-text-primary placeholder:text-text-muted focus:outline-none sm:px-3 sm:text-[12px]"
          disabled={isInputDisabled}
        />
        <button
          type="submit"
          disabled={isSubmitDisabled}
          className="primary-action flex h-9 w-9 items-center justify-center rounded-[9px] disabled:opacity-50"
          title={!connectedWallet ? "Connect wallet to send messages" : isNetworkMismatch ? `Switch wallet to ${NETWORK_CONFIG[selectedNetwork].label}` : ""}
        >
          {isLoading ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <SendHorizontal size={15} />
          )}
        </button>
      </form>
      {uploadError && (
        <div className="mt-2 rounded-[8px] border border-accent-danger bg-accent-danger/10 px-3 py-2 text-[10px] text-accent-danger">
          {uploadError}
        </div>
      )}
    </div>
  );
}
