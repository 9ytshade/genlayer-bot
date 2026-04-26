'use client';

import React, { useState, useRef, useEffect } from 'react';
import MessageComponent from './Message';
import QuickActions from './QuickActions';
import CommandPalette from './CommandPalette';
import { MessageData, sendMessage, confirmAction } from '../lib/api';
import { Send, Bot, Loader2, Command } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ConnectWalletButton from './ConnectWalletButton';

export default function ChatInterface() {
  const [messages, setMessages] = useState<MessageData[]>([{
    id: 'msg-0',
    role: 'bot',
    content: "Hi! I'm your GenLayer AI assistant. You can ask me to check your balance, send tokens, or deploy intelligent contracts. What would you like to do?"
  }]);
  
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [walletAddress, setWalletAddress] = useState<string | null>(null);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [recentCommands, setRecentCommands] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    // Get wallet address from localStorage
    const stored = localStorage.getItem('walletAddress');
    if (stored) {
      setWalletAddress(stored);
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

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
      const response = await sendMessage(userMsg.content);
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
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickAction = (action: string) => {
    setInput(action);
  };

  const handleConfirm = async (msgId: string) => {
    const msg = messages.find(m => m.id === msgId);
    if (!msg || !msg.intent) return;

    // Update status to executing
    setMessages(prev => prev.map(m => 
      m.id === msgId ? { ...m, status: 'executing' } : m
    ));

    try {
      const result = await confirmAction(msg.intent);
      setMessages(prev => prev.map(m => 
        m.id === msgId ? { 
          ...m, 
          status: result.error ? 'error' : 'success',
          txHash: result.txHash,
          content: result.error ? `Execution failed: ${result.error}` : 'Transaction successfully executed on GenLayer.'
        } : m
      ));
    } catch (error) {
       setMessages(prev => prev.map(m => 
        m.id === msgId ? { ...m, status: 'error', content: 'Network error during execution.' } : m
      ));
    }
  };

  const handleCancel = (msgId: string) => {
    setMessages(prev => prev.map(m => 
      m.id === msgId ? { ...m, status: undefined, content: 'Transaction cancelled by user.' } : m
    ));
  };

  const hasPendingAction = messages.some(
    (m) => m.status === 'awaiting_confirmation' || m.status === 'executing'
  );

  return (
    <div className="flex flex-col h-full w-full mx-auto overflow-hidden bg-bg-base border-none md:border-x border-border-default relative">
      
      {/* Header */}
      <div className="h-14 border-b border-border-strong bg-bg-elevated flex items-center justify-between px-6 shrink-0 z-10">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 bg-accent-primary flex items-center justify-center text-black font-bold">
            <Bot size={16} />
          </div>
          <div>
            <h1 className="font-display text-[15px] font-semibold text-text-primary tracking-tight">AI Agent</h1>
            {walletAddress && (
              <p className="text-[10px] text-text-muted font-mono mt-0.5">{walletAddress.slice(0, 10)}...{walletAddress.slice(-8)}</p>
            )}
          </div>
        </div>
        
        <ConnectWalletButton />
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto px-6 py-8 md:px-12 md:py-10 space-y-10 scroll-smooth">
        {messages.length === 1 && (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            <QuickActions onSelectAction={handleQuickAction} />
          </motion.div>
        )}
        
        <AnimatePresence initial={false}>
          {messages.map(msg => (
            <MessageComponent 
              key={msg.id} 
              msg={msg} 
              onConfirm={handleConfirm}
              onCancel={handleCancel}
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
                <div className="px-4 py-3 rounded-2xl bg-white/[0.04] border border-white/10 rounded-tl-md shadow-sm flex items-center gap-2 backdrop-blur-md">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 rounded-full bg-accent-primary/60 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 rounded-full bg-accent-primary/60 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 rounded-full bg-accent-primary/60 animate-bounce" style={{ animationDelay: '300ms' }} />
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
            className="hidden md:flex items-center justify-center p-2 border border-border-strong hover:border-accent-primary text-text-secondary hover:text-accent-primary transition-colors rounded-none"
            title="Open command palette (Cmd+K)"
          >
            <Command size={14} />
          </button>

          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                setCommandPaletteOpen(true);
              }
            }}
            placeholder="> Type a command..."
            className="flex-1 bg-bg-surface border border-border-strong py-3.5 pl-4 pr-14 text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary transition-colors font-mono text-sm rounded-none"
            disabled={isLoading || messages.some(m => m.status === 'awaiting_confirmation' || m.status === 'executing')}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading || messages.some(m => m.status === 'awaiting_confirmation' || m.status === 'executing')}
            className="absolute right-2 p-2 bg-accent-primary text-black hover:bg-white disabled:opacity-50 disabled:bg-border-strong disabled:text-text-muted transition-colors flex items-center justify-center rounded-none"
          >
            {isLoading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Send size={16} />
            )}
          </button>
        </form>
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
