'use client';

import { useState, useEffect } from 'react';
import { useScans } from '@/hooks/useScans';
import { ScanList } from '@/components/scans/ScanList';
import { CreateScanForm } from '@/components/scans/CreateScanForm';
import { useWebSocket } from '@/hooks/useWebSocket';
import type { CreateScanRequest, WebSocketMessage } from '@/types';
import { useRouter } from 'next/navigation';

export default function HomePage() {
  const { scans, loading, error, createScan, deleteScan } = useScans();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const { on } = useWebSocket(null);
  const router = useRouter();

  useEffect(() => {
    setShowCreateForm(false);
  }, []);

  useEffect(() => {
    const unsubscribeCreated = on('scan_created', (message: WebSocketMessage) => {
      if (message.data && typeof message.data === 'object' && 'scan_id' in message.data) {
        setShowCreateForm(false);
        const scanId = message.data.scan_id as string;
        router.push(`/scan/${scanId}`);
      }
    });

    const unsubscribeUpdated = on('scan_updated', () => {
      window.location.reload();
    });

    const unsubscribeDeleted = on('scan_deleted', () => {
      window.location.reload();
    });

    return () => {
      unsubscribeCreated();
      unsubscribeUpdated();
      unsubscribeDeleted();
    };
  }, [on, router]);

  const handleCreateScan = (request: CreateScanRequest) => {
    setShowCreateForm(false);
    
    createScan(request)
      .then(() => {
      })
      .catch((err) => {
        const errorMessage = err instanceof Error ? err.message : 'Unknown error';
        alert(`Failed to create scan: ${errorMessage}`);
      });
  };

  const handleDeleteScan = async (scanId: string) => {
    try {
      await deleteScan(scanId);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      alert(`Failed to delete scan: ${errorMessage}`);
      throw err;
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto overflow-y-auto h-screen">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-4xl text-primary-green">🦉 Strix</h1>
        <button
          onClick={() => setShowCreateForm(true)}
          className="px-6 py-3 bg-primary-green text-white rounded-lg font-semibold text-base transition-colors hover:bg-primary-green-dark"
        >
          Create Scan
        </button>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-error/20 border border-error rounded text-error">
          {error.message}
        </div>
      )}

      {loading ? (
        <div className="text-center py-16 text-text-muted">Loading scans...</div>
      ) : (
        <ScanList scans={scans} onDelete={handleDeleteScan} />
      )}

      {showCreateForm && (
        <CreateScanForm
          onSubmit={handleCreateScan}
          onCancel={() => setShowCreateForm(false)}
        />
      )}
    </div>
  );
}
