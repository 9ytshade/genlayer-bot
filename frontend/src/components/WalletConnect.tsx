'use client';

import { ConnectButton } from '@rainbow-me/rainbowkit';

export default function WalletConnect() {
  return (
    <div className="flex items-center">
      <ConnectButton chainStatus="none" showBalance={false} accountStatus="address" />
    </div>
  );
}
