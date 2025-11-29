'use client';

import { ScanCard } from './ScanCard';
import type { Scan } from '@/types';

interface ScanListProps {
  scans: Scan[];
  onDelete: (scanId: string) => void;
}

export function ScanList({ scans, onDelete }: ScanListProps) {
  if (scans.length === 0) {
    return (
      <div className="text-center py-16 text-text-muted">
        <div className="text-6xl mb-4">🦉</div>
        <p>No scans yet. Create your first scan to get started.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-6">
      {scans.map((scan) => (
        <ScanCard key={scan.scan_id} scan={scan} onDelete={onDelete} />
      ))}
    </div>
  );
}

