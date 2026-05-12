import ChatInterface from '@/components/ChatInterface';
import LiveLogsPanel from '@/components/LiveLogsPanel';

export default function Home() {
  const suggestions = ['[wallet]', '[deploy]', '[simulate]', '[gas]'];

  return (
    <main className="relative h-dvh w-screen overflow-hidden bg-bg-base flex items-center justify-center noise-bg">
      <div className="w-full h-full max-w-[1500px] md:p-8 lg:p-12 z-10 min-h-0">
        <div className="h-full w-full rounded-none md:rounded-lg overflow-hidden border border-border-default bg-bg-surface shadow-2xl flex flex-col min-h-0">
          <div className="h-12 border-b border-border-strong bg-bg-elevated px-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-[14px] font-display font-medium tracking-wide text-text-primary">GENLAYER</span>
              <span className="text-[10px] uppercase tracking-[0.2em] text-accent-primary">Terminal</span>
            </div>
            <div className="hidden md:flex items-center gap-2">
              <div className="h-2.5 w-2.5 rounded-sm bg-accent-primary" />
              <div className="h-2.5 w-2.5 rounded-sm bg-border-strong" />
              <div className="h-2.5 w-2.5 rounded-sm bg-border-strong" />
            </div>
          </div>

          <div className="flex-1 min-h-0 w-full grid grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)_300px]">
            {/* Left contacts panel */}
            <aside className="hidden lg:flex min-h-0 flex-col border-r border-border-default bg-bg-elevated p-6">
              <div className="mb-6 rounded-none bg-black border border-border-strong px-4 py-3 text-[10px] uppercase tracking-widest text-text-muted">
                Connections
              </div>
              <div className="text-[10px] uppercase tracking-widest text-text-muted font-mono px-4 pt-4">
                No active connections
              </div>
            </aside>

            {/* Center chat */}
            <section className="min-w-0 bg-bg-base h-full flex flex-col overflow-hidden">
              <ChatInterface />
            </section>

            {/* Right activity panel */}
            <aside className="hidden lg:flex min-h-0 flex-col border-l border-border-default bg-bg-elevated p-6 gap-6 overflow-hidden">
              <LiveLogsPanel />

              <div className="shrink-0 rounded-none border border-border-strong bg-bg-base p-3">
                <h3 className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-2 font-mono">Cmds</h3>
                <div className="flex flex-wrap gap-2">
                  {suggestions.map((item) => (
                    <span
                      key={item}
                      className="text-[11px] font-mono px-2 py-1 bg-border-subtle border border-border-strong text-text-secondary hover:text-accent-primary hover:border-accent-primary cursor-pointer transition-colors"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            </aside>
          </div>
        </div>
      </div>
    </main>
  );
}
