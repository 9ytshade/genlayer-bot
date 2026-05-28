import ChatInterface from '@/components/ChatInterface';
import LiveLogsPanel from '@/components/LiveLogsPanel';
import GenLayerLogo from '@/components/GenLayerLogo';

export default function Home() {
  const suggestions = ['wallet', 'deploy', 'simulate', 'gas'];

  return (
    <main className="relative flex h-dvh w-screen items-center justify-center overflow-hidden bg-bg-base noise-bg">
      <div className="z-10 h-full min-h-0 w-full max-w-[1560px] p-0 md:p-6 lg:p-10">
        <div className="surface-shell flex h-full min-h-0 w-full flex-col overflow-hidden rounded-none md:rounded-[14px]">
          <div className="flex min-h-16 shrink-0 items-center justify-between gap-4 border-b border-border-default bg-bg-elevated px-5 py-4 md:px-7">
            <div className="flex min-w-0 items-center gap-4">
              <div className="flex h-11 shrink-0 items-center rounded-full border border-accent-primary/45 bg-accent-primary/10 px-4 text-text-primary shadow-[0_0_22px_rgba(255,176,0,0.12)]">
                <GenLayerLogo className="h-7 w-32" />
              </div>
              <div className="min-w-0">
                <div className="truncate font-display text-[17px] font-semibold text-text-primary">AI Chatbot</div>
                <div className="micro-label mt-1 hidden sm:block">Wallet-native contract operations</div>
              </div>
            </div>
            <div className="hidden items-center gap-2 md:flex">
              <span className="status-pill text-accent-success">Studionet ready</span>
            </div>
          </div>

          <div className="grid min-h-0 flex-1 w-full grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px]">
            <section className="flex h-full min-w-0 flex-col overflow-hidden bg-bg-base">
              <ChatInterface />
            </section>

            <aside className="hidden min-h-0 flex-col gap-5 overflow-hidden border-l border-border-default bg-bg-elevated p-5 lg:flex">
              <LiveLogsPanel />

              <div className="panel-soft shrink-0 rounded-[12px] p-4">
                <h3 className="micro-label mb-3">Command index</h3>
                <div className="flex flex-wrap gap-2">
                  {suggestions.map((item) => (
                    <span
                      key={item}
                      className="rounded-full border border-border-strong bg-bg-base px-2.5 py-1 font-mono text-[11px] text-text-secondary transition-colors hover:border-accent-primary hover:text-accent-primary"
                    >
                      /{item}
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
