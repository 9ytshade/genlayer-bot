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

  return (
    <div className="rounded-none border border-border-strong bg-bg-base p-3 h-full min-h-0 flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-[10px] uppercase tracking-[0.2em] text-text-secondary font-mono">Logs</h3>
        <span className={`text-[10px] font-mono ${status === 'live' ? 'text-accent-success' : 'text-text-muted'}`}>
          {statusLabel}
        </span>
      </div>

      <div className="space-y-2 overflow-y-auto pr-1 min-h-0">
        {logs.length === 0 ? (
          <div className="text-[11px] text-text-muted font-mono border border-border-subtle p-2">
            Waiting for events...
          </div>
        ) : (
          logs.slice().reverse().map((log, idx) => (
            <div key={`${log.timestamp}-${idx}`} className="rounded-none border-l-2 border-accent-primary bg-bg-elevated p-2.5">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] font-mono font-bold text-accent-primary">{log.event}</p>
                <span className="text-[9px] text-text-muted font-mono">{new Date(log.timestamp).toLocaleTimeString()}</span>
              </div>
              <p className="text-[11px] text-text-secondary mt-0.5 leading-relaxed">{log.message}</p>
              {log.meta && Object.keys(log.meta).length > 0 && (
                <pre className="mt-1 text-[10px] text-text-muted font-mono whitespace-pre-wrap break-words">
                  {JSON.stringify(log.meta)}
                </pre>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
