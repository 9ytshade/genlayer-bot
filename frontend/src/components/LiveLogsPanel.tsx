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

export default function LiveLogsPanel({ compact = false }: { compact?: boolean }) {
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
    <div className="panel flex min-h-0 flex-1 flex-col overflow-hidden rounded-[12px]">
      <div className="flex shrink-0 items-center justify-between border-b border-border-default bg-bg-elevated px-4 py-3">
        <div className="flex items-center gap-2">
          <div className={`h-1.5 w-1.5 rounded-full ${status === 'live' ? 'bg-accent-success animate-pulse' : 'bg-text-muted'}`} />
          <div>
            <h3 className="font-display text-[13px] font-semibold text-text-primary">Activity Monitor</h3>
            <div className="micro-label mt-1">Live validation and deploy logs</div>
          </div>
        </div>
        <span className={`status-pill ${
          status === 'live' ? 'text-accent-success' : 'text-text-muted'
        }`}>
          {statusLabel}
        </span>
      </div>

      <div className={`min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain px-3 py-3 ${compact ? 'pb-14 lg:pb-3' : ''}`}>
        {logs.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center space-y-3 opacity-60">
            <div className="flex h-8 w-8 items-center justify-center rounded-full border border-dashed border-border-strong">
              <div className="h-1 w-1 animate-ping rounded-full bg-accent-primary" />
            </div>
            <p className="micro-label">Awaiting events</p>
          </div>
        ) : (
          logs.slice().reverse().map((log, idx) => (
            <div 
              key={`${log.timestamp}-${idx}`} 
              className={`rounded-[8px] border p-3 transition-transform hover:translate-x-0.5 ${getLevelColor(log.level)}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-col gap-1">
                  <span className="font-mono text-[9px] uppercase tracking-[0.08em] opacity-60">
                    [{new Date(log.timestamp).toLocaleTimeString()}] {log.event}
                  </span>
                  <p className="text-[11px] font-medium leading-relaxed">{log.message}</p>
                </div>
              </div>
              {log.meta && Object.keys(log.meta).length > 0 && (
                <div className="mt-2 pt-2 border-t border-current/10 overflow-hidden">
                  <pre className="whitespace-pre-wrap break-all rounded-[6px] bg-black/20 p-2 font-mono text-[10px] opacity-70">
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
