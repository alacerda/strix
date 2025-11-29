'use client';

import type { Vulnerability } from '@/types';

interface SeverityBreakdownProps {
  vulnerabilities: Vulnerability[];
}

export function SeverityBreakdown({ vulnerabilities }: SeverityBreakdownProps) {
  const breakdown = vulnerabilities.reduce(
    (acc, vuln) => {
      acc[vuln.severity] = (acc[vuln.severity] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  const getSeverityClass = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-critical text-white';
      case 'high':
        return 'bg-high text-white';
      case 'medium':
        return 'bg-medium text-white';
      case 'low':
        return 'bg-low text-white';
      case 'info':
        return 'bg-info text-white';
      default:
        return 'bg-text-muted text-white';
    }
  };

  const severities: Array<{ name: string; count: number }> = [
    { name: 'critical', count: breakdown.critical || 0 },
    { name: 'high', count: breakdown.high || 0 },
    { name: 'medium', count: breakdown.medium || 0 },
    { name: 'low', count: breakdown.low || 0 },
    { name: 'info', count: breakdown.info || 0 },
  ];

  return (
    <div className="p-4 border-b border-border-color">
      <h3 className="text-base mb-4 text-primary-green">Severity Breakdown</h3>
      <div className="flex flex-wrap gap-2">
        {severities.map(({ name, count }) => (
          <span
            key={name}
            className={`inline-block px-2 py-1 rounded text-xs font-semibold ${getSeverityClass(name)}`}
          >
            {name}: {count}
          </span>
        ))}
      </div>
    </div>
  );
}

