'use client';

import type { Agent } from '@/types';

interface AgentNodeProps {
  agent: Agent;
  isSelected: boolean;
  onClick: () => void;
  children?: React.ReactNode;
}

export function AgentNode({ agent, isSelected, onClick, children }: AgentNodeProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'text-success';
      case 'completed':
        return 'text-info';
      case 'stopped':
        return 'text-warning';
      case 'failed':
        return 'text-error';
      default:
        return 'text-text-muted';
    }
  };

  return (
    <div>
      <div
        onClick={onClick}
        className={`p-2 my-1 rounded cursor-pointer transition-colors select-none ${
          isSelected
            ? 'bg-primary-green/20 border border-primary-green'
            : 'hover:bg-bg-tertiary'
        }`}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm">🤖</span>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-text-primary truncate">
              {agent.name}
            </div>
            <div className="text-xs text-text-muted truncate">{agent.task}</div>
          </div>
          <span className={`text-xs font-semibold ${getStatusColor(agent.status)}`}>
            {agent.status}
          </span>
        </div>
      </div>
      {children && <div className="ml-4">{children}</div>}
    </div>
  );
}

