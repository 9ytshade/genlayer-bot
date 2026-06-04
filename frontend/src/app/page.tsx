import ChatInterface from '@/components/ChatInterface';

export default function Home() {
  return (
    <main className="relative flex h-dvh w-screen items-center justify-center overflow-hidden bg-bg-base noise-bg">
      <div className="z-10 h-full min-h-0 w-full">
        <ChatInterface />
      </div>
    </main>
  );
}
