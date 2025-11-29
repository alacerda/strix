'use client';

import type { Stats } from '@/types';

interface StatsPanelProps {
  stats: Stats;
}

export function StatsPanel({ stats }: StatsPanelProps) {
  return (
    <div className="p-4 border-b border-border-color">
      <h3 className="text-base mb-4 text-primary-green">Statistics</h3>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between py-2">
          <span className="text-text-secondary">Agents</span>
          <span className="text-text-primary font-semibold">{stats.agents}</span>
        </div>
        <div className="flex justify-between py-2">
          <span className="text-text-secondary">Tools</span>
          <span className="text-text-primary font-semibold">{stats.tools}</span>
        </div>
        <div className="flex justify-between py-2">
          <span className="text-text-secondary">Vulnerabilities</span>
          <span className="text-text-primary font-semibold">{stats.vulnerabilities}</span>
        </div>
        <div className="pt-4 border-t border-border-color mt-4">
          <div className="text-xs text-text-muted mb-2">LLM Stats</div>
          <div className="space-y-1 text-xs">
            <div className="flex justify-between">
              <span className="text-text-secondary">Input Tokens</span>
              <span className="text-text-primary">{stats.llm_stats.input_tokens.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Output Tokens</span>
              <span className="text-text-primary">{stats.llm_stats.output_tokens.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Cached Tokens</span>
              <span className="text-text-primary">{stats.llm_stats.cached_tokens.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Cost</span>
              <span className="text-text-primary">${stats.llm_stats.cost.toFixed(4)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

