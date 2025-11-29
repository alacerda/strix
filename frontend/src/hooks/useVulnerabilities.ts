import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import type { Vulnerability } from '@/types';

export function useVulnerabilities(scanId: string) {
  const [vulnerabilities, setVulnerabilities] = useState<Vulnerability[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const loadVulnerabilities = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.vulnerabilities.list(scanId);
      setVulnerabilities(data.vulnerabilities);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load vulnerabilities'));
    } finally {
      setLoading(false);
    }
  }, [scanId]);

  useEffect(() => {
    loadVulnerabilities();
  }, [loadVulnerabilities]);

  return {
    vulnerabilities,
    loading,
    error,
    loadVulnerabilities,
  };
}

