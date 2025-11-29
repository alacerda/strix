'use client';

import { AgentNode } from './AgentNode';
import type { Agent } from '@/types';

interface AgentsTreeProps {
  agents: Record<string, Agent>;
  selectedAgentId: string | null;
  onSelectAgent: (agentId: string) => void;
}

export function AgentsTree({ agents, selectedAgentId, onSelectAgent }: AgentsTreeProps) {
  const buildTree = () => {
    const agentMap = new Map<string, Agent>();
    const childrenMap = new Map<string, Agent[]>();

    Object.values(agents).forEach((agent) => {
      agentMap.set(agent.agent_id, agent);
      if (agent.parent_id) {
        if (!childrenMap.has(agent.parent_id)) {
          childrenMap.set(agent.parent_id, []);
        }
        childrenMap.get(agent.parent_id)!.push(agent);
      }
    });

    const rootAgents = Object.values(agents).filter((agent) => !agent.parent_id);

    const renderAgent = (agent: Agent): React.ReactNode => {
      const children = childrenMap.get(agent.agent_id) || [];
      return (
        <AgentNode
          key={agent.agent_id}
          agent={agent}
          isSelected={selectedAgentId === agent.agent_id}
          onClick={() => onSelectAgent(agent.agent_id)}
        >
          {children.length > 0 && children.map((child) => renderAgent(child))}
        </AgentNode>
      );
    };

    return rootAgents.map((agent) => renderAgent(agent));
  };

  if (Object.keys(agents).length === 0) {
    return (
      <div className="text-center py-8 text-text-muted text-sm">
        No agents yet
      </div>
    );
  }

  return <div className="space-y-1">{buildTree()}</div>;
}

