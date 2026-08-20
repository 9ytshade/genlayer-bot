import { notFound } from 'next/navigation';
import Phase9ProofClient from './phase9-proof-client';

export default function Phase9ProofPage() {
  if (process.env.NODE_ENV !== 'development') {
    notFound();
  }

  return <Phase9ProofClient />;
}
