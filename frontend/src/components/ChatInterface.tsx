'use client';

import React, { useState, useRef, useEffect } from 'react';
import MessageComponent from './Message';
import QuickActions from './QuickActions';
import CommandPalette from './CommandPalette';
import ConnectWalletButton from './ConnectWalletButton';
import type { Intent } from '../lib/api';
import { MessageData, sendMessage, confirmAction, buildTransferTx, buildDeployTx, validateContractFile } from '../lib/api';
import { Send, Bot, Loader2, Command, FileText } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWallet } from '@/context/WalletContext';
import { useChainId } from 'wagmi';
import { DEFAULT_NETWORK, NETWORK_CONFIG, type NetworkKey } from '@/config';
import { parseEther } from 'viem';

function normalizeDeployIntentForUi(intent: Intent, fileName?: string): Intent {
  const contractName = intent.contract_name || fileName?.replace(/\.py$/i, '') || 'IntelligentContract';
  return {
    ...intent,
    action: 'deploy_contract',
    contract_name: contractName,
    source_file_name: fileName || intent.source_file_name,
    constructor_args_text: intent.constructor_args_text || JSON.stringify(intent.constructor_args || [], null, 2),
    constructor_kwargs_text: intent.constructor_kwargs_text || JSON.stringify(intent.constructor_kwargs || {}, null, 2),
    deploy_value_text: intent.deploy_value_text || String(intent.deploy_value ?? 0),
    gas_limit_text: intent.gas_limit_text || (intent.gas_limit ? String(intent.gas_limit) : ''),
    consensus_max_rotations_text:
      intent.consensus_max_rotations_text || (intent.consensus_max_rotations ? String(intent.consensus_max_rotations) : ''),
  };
}

function parseDeployIntent(intent: Intent) {
  const constructorArgs = JSON.parse((intent.constructor_args_text || '[]').trim() || '[]');
  if (!Array.isArray(constructorArgs)) {
    throw new Error('Constructor args must be a JSON array.');
  }

  const constructorKwargs = JSON.parse((intent.constructor_kwargs_text || '{}').trim() || '{}');
  if (constructorKwargs === null || Array.isArray(constructorKwargs) || typeof constructorKwargs !== 'object') {
    throw new Error('Constructor kwargs must be a JSON object.');
  }

  const deployValueText = (intent.deploy_value_text || '0').trim();
  const deployValueWei = parseEther(deployValueText || '0').toString();
  const gasLimit = intent.gas_limit_text?.trim() ? Number(intent.gas_limit_text) : null;
  if (gasLimit !== null && (!Number.isInteger(gasLimit) || gasLimit < 21000)) {
    throw new Error('Gas limit must be an integer greater than or equal to 21000.');
  }

  const consensusMaxRotations = intent.consensus_max_rotations_text?.trim()
    ? Number(intent.consensus_max_rotations_text)
    : null;
  if (consensusMaxRotations !== null && (!Number.isInteger(consensusMaxRotations) || consensusMaxRotations < 1)) {
    throw new Error('Consensus rotations must be a positive integer.');
  }

  return {
    ...intent,
    constructor_args: constructorArgs,
    constructor_kwargs: constructorKwargs as Record<string, unknown>,
    deploy_value: Number(deployValueText || '0'),
    gas_limit: gasLimit,
    consensus_max_rotations: consensusMaxRotations,
    leader_only: Boolean(intent.leader_only),
    deploy_value_text: deployValueText || '0',
    deploy_value_wei: deployValueWei,
  };
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<MessageData[]>([{
    id: 'msg-0',
    role: 'bot',
    content: "Hi! I'm your GenLayer AI assistant. You can ask me to check your balance, send tokens, or deploy intelligent contracts. What would you like to do?"
  }]);
  
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const { account: connectedWallet } = useWallet();
  const [selectedNetwork, setSelectedNetwork] = useState<NetworkKey>(DEFAULT_NETWORK);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [recentCommands, setRecentCommands] = useState<string[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chainId = useChainId();

  useEffect(() => {
    const timer = window.setTimeout(() => setIsMounted(true), 0);
    return () => window.clearTimeout(timer);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const isNetworkMismatch = Boolean(
    connectedWallet && chainId && chainId !== NETWORK_CONFIG[selectedNetwork].chainId
  );

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!connectedWallet || isNetworkMismatch) return;
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError(null);

    if (!file.name.endsWith('.py')) {
      const errorMessage = `Only Python contract files are supported. '${file.name}' is not a .py file.`;
      setUploadError(errorMessage);
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'bot',
        content: errorMessage,
        status: 'error',
      }]);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = async (event) => {
      const content = event.target?.result as string;
      if (!content) return;

      // Automatically send the deployment command with the code
      const deployCmd = `Deploy this contract:\n\n${content}`;
      
      const userMsg: MessageData = {
        id: Date.now().toString(),
        role: 'user',
        content: `Uploaded file: ${file.name}`
      };

      setMessages(prev => [...prev, userMsg]);
      setIsLoading(true);

      try {
        const validation = await validateContractFile(content, file.name);
        if (!validation.valid) {
          const details = [...validation.errors, ...validation.warnings].join('\n');
          const botMsg: MessageData = {
            id: (Date.now() + 1).toString(),
            role: 'bot',
            content: `${validation.message}${details ? `\n\n${details}` : ''}`,
            status: 'error',
          };
          setUploadError(validation.message);
          setMessages(prev => [...prev, botMsg]);
          return;
        }

        const response = await sendMessage(deployCmd, connectedWallet ?? undefined, selectedNetwork);
        const normalizedIntent = response.intent && response.intent.action === 'deploy_contract'
          ? normalizeDeployIntentForUi({ ...(response.intent as Intent), code: content }, file.name)
          : {
              action: 'deploy_contract',
              code: content,
              contract_name: file.name.replace(/\.py$/i, ''),
              source_file_name: file.name,
              constructor_args_text: '[]',
              constructor_kwargs_text: '{}',
              deploy_value_text: '0',
              gas_limit_text: '',
              consensus_max_rotations_text: '',
              leader_only: false,
            } satisfies Intent;
        const botMsg: MessageData = {
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content: [
            response.content || `Contract file '${file.name}' is ready for Studionet deployment. Review the parameters below and confirm when you are ready.`,
            ...validation.warnings,
          ].join('\n\n'),
          intent: normalizedIntent,
          simulation: response.simulation,
          status: response.status === 'error' ? 'error' : 'awaiting_confirmation'
        };
        setMessages(prev => [...prev, botMsg]);
      } catch (error) {
        console.error(error);
        const message = error instanceof Error ? error.message : 'Unable to validate the uploaded contract.';
        setUploadError(message);
        setMessages(prev => [...prev, {
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content: message,
          status: 'error',
        }]);
      } finally {
        setIsLoading(false);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
    };
    reader.readAsText(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!connectedWallet || !input.trim() || isLoading || isNetworkMismatch) return;

    const userMsg: MessageData = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim()
    };

    // Add to recent commands
    setRecentCommands(prev => [input.trim(), ...prev].slice(0, 5));

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await sendMessage(userMsg.content, connectedWallet ?? undefined, selectedNetwork);
      const botMsg: MessageData = {
        id: (Date.now() + 1).toString(),
        role: 'bot',
        content: response.content || 'An error occurred.',
        intent: response.intent,
        simulation: response.simulation,
        status: response.status
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'Failed to reach the server. Please try again.';
      setMessages(prev => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content: message,
          status: 'error',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const { sendTransaction } = useWallet();

  const handleConfirm = async (msgId: string) => {
    const msg = messages.find(m => m.id === msgId);
    if (!msg || !msg.intent) return;

    if (!connectedWallet) {
      setMessages(prev => prev.map(m => 
        m.id === msgId ? { ...m, status: 'error', content: 'Wallet not connected' } : m
      ));
      return;
    }

    // Update status to executing
    setMessages(prev => prev.map(m => 
      m.id === msgId ? { ...m, status: 'executing' } : m
    ));

    try {
      const intent = msg.intent;
      let intentForConfirmation = intent;
      let txHash: string | undefined = undefined;

      // For transfers and deployments, let the user's wallet broadcast the transaction.
      if (intent.action === 'transfer') {
        if (!intent.recipient || typeof intent.amount !== 'number') {
          throw new Error('Transfer intent is missing recipient or amount.');
        }
        const txData = await buildTransferTx(intent.recipient, intent.amount, connectedWallet as string, selectedNetwork);
        txHash = await sendTransaction({
          to: txData.to,
          value: txData.value,
          data: txData.data,
          chainId: txData.chainId,
          nonce: txData.nonce,
          gas: txData.gas,
          gasPrice: txData.gasPrice,
        });
      } else if (intent.action === 'deploy_contract') {
        if (!intent.code) {
          throw new Error('Deployment intent is missing contract code.');
        }
        const deployIntent = parseDeployIntent(intent);
        intentForConfirmation = deployIntent;
        const txData = await buildDeployTx(
          {
            code: deployIntent.code as string,
            constructor_args: deployIntent.constructor_args,
            constructor_kwargs: deployIntent.constructor_kwargs as Record<string, unknown>,
            deploy_value_wei: deployIntent.deploy_value_wei as string,
            gas_limit: deployIntent.gas_limit as number | null,
            consensus_max_rotations: deployIntent.consensus_max_rotations as number | null,
            leader_only: deployIntent.leader_only as boolean,
          },
          connectedWallet as string,
          selectedNetwork
        );
        txHash = await sendTransaction({
          to: txData.to,
          data: txData.data,
          value: txData.value,
          chainId: txData.chainId,
          nonce: txData.nonce,
          gas: txData.gas,
          gasPrice: txData.gasPrice,
          maxFeePerGas: txData.maxFeePerGas,
          maxPriorityFeePerGas: txData.maxPriorityFeePerGas,
        });
      }

      const result = await confirmAction(intentForConfirmation, connectedWallet, undefined, txHash, selectedNetwork);
      setMessages(prev => prev.map(m => 
        m.id === msgId ? { 
          ...m, 
          status: result.error ? 'error' : 'success',
          intent: intentForConfirmation,
          txHash: result.txHash,
          consensusTxId: result.consensusTxId,
          contractAddress: result.contractAddress,
          derivedAddresses: result.derivedAddresses,
          content: result.error
            ? `Execution failed: ${result.error}`
            : result.balance !== undefined
              ? `Your wallet balance is ${result.balance} GEN.`
              : result.content || 'Transaction successfully executed on GenLayer.'
        } : m
      ));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Network error during execution.';
      setMessages(prev => prev.map(m => 
        m.id === msgId ? { ...m, status: 'error', content: errorMessage } : m
      ));
    }
  };

  const handleCancel = (msgId: string) => {
    setMessages(prev => prev.map(m => 
      m.id === msgId ? { ...m, status: undefined, content: 'Transaction cancelled by user.' } : m
    ));
  };

  const handleQuickAction = (command: string) => {
    setInput(command);
    setRecentCommands(prev => [command, ...prev.filter((item) => item !== command)].slice(0, 5));
  };

  const handleIntentUpdate = (msgId: string, patch: Partial<Intent>) => {
    setMessages(prev => prev.map(message => {
      if (message.id !== msgId || !message.intent) {
        return message;
      }
      return {
        ...message,
        intent: {
          ...message.intent,
          ...patch,
        },
      };
    }));
  };

  if (!isMounted) return null;

  return (
    <div className="flex flex-col h-full min-h-0 w-full mx-auto overflow-hidden bg-bg-base border-none md:border-x border-border-default relative">
      
      {/* Header */}
      <div className="h-14 border-b border-border-strong bg-bg-elevated flex items-center justify-between px-6 shrink-0 z-10">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 bg-accent-primary flex items-center justify-center text-black font-bold">
            <Bot size={16} />
          </div>
          <div>
            <h1 className="font-display text-[15px] font-semibold text-text-primary tracking-tight">AI Agent</h1>
            {connectedWallet && (
              <p className="text-[10px] text-text-muted font-mono mt-0.5">{connectedWallet.slice(0, 10)}...{connectedWallet.slice(-8)}</p>
            )}
          </div>
        </div>
        
         <div className="flex items-center gap-2">
           <label htmlFor="network-select" className="text-[10px] uppercase tracking-widest text-text-muted font-mono">
             Network
           </label>
           <select
             id="network-select"
             value={selectedNetwork}
             onChange={(e) => setSelectedNetwork(e.target.value as NetworkKey)}
             className="bg-black border border-border-strong px-2 py-1 text-[11px] font-mono text-text-secondary focus:outline-none focus:border-accent-primary"
           >
             {Object.entries(NETWORK_CONFIG).map(([key, cfg]) => (
               <option key={key} value={key}>
                 {cfg.label}
               </option>
             ))}
           </select>
           <ConnectWalletButton network={selectedNetwork} />
         </div>
      </div>

      {/* Chat Area */}
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-6 md:px-12 md:py-10 space-y-8 md:space-y-10 scroll-smooth">
        {!connectedWallet && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg"
          >
            <p className="text-yellow-800 text-sm font-medium">
              Please connect your wallet to get started.
            </p>
          </motion.div>
        )}

        {messages.length === 1 && connectedWallet && (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
             <QuickActions onSelectAction={handleQuickAction} />
           </motion.div>
         )}
         {connectedWallet && (
           <div className="text-[10px] uppercase tracking-widest text-text-muted font-mono">
             Active network: {NETWORK_CONFIG[selectedNetwork].label}
           </div>
         )}
         {connectedWallet && isNetworkMismatch && (
           <div className="rounded-xl border border-yellow-400/60 bg-yellow-50 px-3 py-2 text-[11px] font-mono text-yellow-900">
             Wallet is connected to the wrong chain. Please switch your wallet to {NETWORK_CONFIG[selectedNetwork].label} or use the wallet prompt to switch networks.
           </div>
         )}
        
        <AnimatePresence initial={false}>
          {messages.map(msg => (
            <MessageComponent 
              key={msg.id} 
              msg={msg} 
              onConfirm={handleConfirm}
              onCancel={handleCancel}
              onUpdateIntent={handleIntentUpdate}
            />
          ))}
          {isLoading && (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-4 max-w-3xl"
            >
              <div className="shrink-0 w-9 h-9 rounded-xl bg-slate-900/90 border border-white/15 text-text-secondary flex items-center justify-center shadow-sm">
                <Bot size={16} />
              </div>
              <div className="flex flex-col gap-1 items-start">
                <span className="text-xs text-text-muted font-medium ml-1">GenLayer AI</span>
                <div className="px-4 py-3 rounded-2xl bg-white/4 border border-white/10 rounded-tl-md shadow-sm flex items-center gap-2 backdrop-blur-md">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 rounded-full bg-accent-primary/60 animate-bounce delay-0" />
                    <span className="w-2 h-2 rounded-full bg-accent-primary/60 animate-bounce delay-150" />
                    <span className="w-2 h-2 rounded-full bg-accent-primary/60 animate-bounce delay-300" />
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={messagesEndRef} className="h-4" />
      </div>

      {/* Input Area */}
      <div className="p-6 md:px-12 bg-bg-base border-t border-border-strong shrink-0">
        <form onSubmit={handleSubmit} className="relative flex items-center gap-2 w-full mx-auto">
          <button
            type="button"
            onClick={() => setCommandPaletteOpen(true)}
            disabled={!connectedWallet}
            className="hidden md:flex items-center justify-center p-2 border border-border-strong hover:border-accent-primary text-text-secondary hover:text-accent-primary disabled:opacity-50 disabled:cursor-not-allowed transition-colors rounded-none"
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
            className="flex items-center justify-center p-2 border border-border-strong hover:border-accent-primary text-text-secondary hover:text-accent-primary disabled:opacity-50 disabled:cursor-not-allowed transition-colors rounded-none"
            title="Upload Intelligent Contract (.py)"
          >
            <FileText size={14} />
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
            placeholder={connectedWallet ? "> Type a command..." : "Connect wallet to chat..."}
            className="flex-1 bg-bg-surface border border-border-strong py-3.5 pl-4 pr-14 text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary transition-colors font-mono text-sm rounded-none"
            disabled={!connectedWallet || isLoading || messages.some(m => m.status === 'awaiting_confirmation' || m.status === 'executing')}
          />
          <button
            type="submit"
            disabled={!connectedWallet || !input.trim() || isLoading || isNetworkMismatch || messages.some(m => m.status === 'awaiting_confirmation' || m.status === 'executing')}
            className="absolute right-2 p-2 bg-accent-primary text-black hover:bg-white disabled:opacity-50 disabled:bg-border-strong disabled:text-text-muted transition-colors flex items-center justify-center rounded-none"
            title={!connectedWallet ? "Connect wallet to send messages" : isNetworkMismatch ? `Switch wallet to ${NETWORK_CONFIG[selectedNetwork].label}` : ""}
          >
            {isLoading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Send size={16} />
            )}
          </button>
        </form>
        {uploadError && (
          <div className="mt-3 border border-accent-danger bg-accent-danger/10 px-3 py-2 text-[11px] text-accent-danger">
            {uploadError}
          </div>
        )}
        <div className="flex justify-between mt-2 text-[10px] text-text-muted font-mono uppercase tracking-widest px-1">
          <span>Mode: Natural Language</span>
          <span className="hidden md:block">Cmd+K: Commands</span>
          <span>Security: Active</span>
        </div>
      </div>

      {/* Command Palette */}
      <CommandPalette 
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        onSelectCommand={(cmd) => {
          setInput(cmd);
          setCommandPaletteOpen(false);
        }}
        recentCommands={recentCommands}
      />
    </div>
  );
}
