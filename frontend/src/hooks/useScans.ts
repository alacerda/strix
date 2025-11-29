import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import type { Scan, CreateScanRequest } from '@/types';

export function useScans() {
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const loadScans = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.scans.list();
      setScans(data.scans);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load scans'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadScans();
  }, [loadScans]);

  const createScan = useCallback(
    async (request: CreateScanRequest): Promise<Scan> => {
      try {
        setError(null);
        const scan = await api.scans.create(request);
        await loadScans();
        return scan;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to create scan');
        setError(error);
        throw error;
      }
    },
    [loadScans]
  );

  const deleteScan = useCallback(
    async (scanId: string): Promise<void> => {
      try {
        setError(null);
        await api.scans.delete(scanId);
        await loadScans();
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to delete scan');
        setError(error);
        throw error;
      }
    },
    [loadScans]
  );

  const stopScan = useCallback(
    async (scanId: string): Promise<void> => {
      try {
        setError(null);
        await api.scans.stop(scanId);
        await loadScans();
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to stop scan');
        setError(error);
        throw error;
      }
    },
    [loadScans]
  );

  return {
    scans,
    loading,
    error,
    loadScans,
    createScan,
    deleteScan,
    stopScan,
  };
}

