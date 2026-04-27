'use client';

import { useEffect, useMemo, useState } from 'react';
import { API_BASE_URL } from '@/config';

interface LogItem {
  timestamp: string;
  level: string;
  event: string;
  message: string;
  meta?: Record<string, unknown>;
}

const MAX_ITEMS = 80;

function getWsUrl(): string {
  const apiBase = API_BASE_URL;
  const normalized = apiBase.replace(/\/$/, '');
  const wsBase = normalized.replace(/^http/, 'ws');
  return `${wsBase}/logs/stream`;
}

export default function LiveLogsPanel() {
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [status, setStatus] = useState<'connecting' | 'live' | 'offline'>('connecting');

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let unmounted = false;

    const connect = () => {
      setStatus('connecting');
      ws = new WebSocket(getWsUrl());

      ws.onopen = () => {
        if (!unmounted) setStatus('live');
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'backlog' && Array.isArray(payload.items)) {
            setLogs(payload.items.slice(-MAX_ITEMS));
            return;
          }

          if (payload.type === 'log' && payload.item) {
            setLogs((prev) => [...prev, payload.item].slice(-MAX_ITEMS));
          }
        } catch {
          // Ignore malformed payloads and keep stream alive.
        }
      };

      ws.onclose = () => {
        if (unmounted) return;
        setStatus('offline');
        retryTimer = setTimeout(connect, 1500);
      };

      ws.onerror = () => {
        ws?.close();
      };
    };

    connect();

    return () => {
      unmounted = true;
      if (retryTimer) clearTimeout(retryTimer);
      ws?.close();
    };
  }, []);

  const statusLabel = useMemo(() => {
    if (status === 'live') return 'LIVE';
    if (status === 'connecting') return 'CONNECTING';
    return 'OFFLINE';
  }, [status]);

  const getLevelColor = (level: string) => {
    switch (level.toUpperCase()) {
      case 'SUCCESS': return 'text-accent-success border-accent-success/50 bg-accent-success/5';
      case 'ERROR': return 'text-red-400 border-red-500/50 bg-red-500/5';
      case 'WARN': return 'text-yellow-400 border-yellow-500/50 bg-yellow-500/5';
      default: return 'text-accent-primary border-accent-primary/50 bg-accent-primary/5';
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0 bg-bg-surface overflow-hidden">
      <div className="flex items-center justify-between p-4 border-b border-border-strong bg-bg-elevated shrink-0">
        <div className="flex items-center gap-2">
          <div className={`w-1.5 h-1.5 rounded-full ${status === 'live' ? 'bg-accent-success animate-pulse' : 'bg-text-muted'}`} />
          <h3 className="text-[11px] uppercase tracking-[0.2em] text-text-primary font-bold font-display">System Operations</h3>
        </div>
        <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
          status === 'live' ? 'text-accent-success border-accent-success/30' : 'text-text-muted border-border-strong'
        }`}>
          {statusLabel}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-border-strong">
        {logs.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center opacity-50 space-y-3">
            <div className="w-8 h-8 border border-dashed border-border-strong rounded-full flex items-center justify-center">
              <div className="w-1 h-1 bg-accent-primary rounded-full animate-ping" />
            </div>
            <p className="text-[11px] font-mono uppercase tracking-widest">Awaiting system events...</p>
          </div>
        ) : (
          logs.slice().reverse().map((log, idx) => (
            <div 
              key={`${log.timestamp}-${idx}`} 
              className={`rounded-none border p-3 transition-all hover:translate-x-1 ${getLevelColor(log.level)}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-col gap-1">
                  <span className="text-[9px] font-mono opacity-60 uppercase tracking-wider">
                    [{new Date(log.timestamp).toLocaleTimeString()}] {log.event}
                  </span>
                  <p className="text-[12px] font-medium leading-relaxed">{log.message}</p>
                </div>
              </div>
              {log.meta && Object.keys(log.meta).length > 0 && (
                <div className="mt-2 pt-2 border-t border-current/10 overflow-hidden">
                  <pre className="text-[10px] font-mono opacity-70 whitespace-pre-wrap break-all bg-black/20 p-2">
                    {JSON.stringify(log.meta, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
