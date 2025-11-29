'use client';

import type { ChatMessage, ToolExecution } from '@/types';

interface MessageListProps {
  messages: ChatMessage[];
  toolExecutions: ToolExecution[];
}

export function MessageList({ messages, toolExecutions }: MessageListProps) {
  const combinedItems: Array<{ type: 'message' | 'tool'; data: ChatMessage | ToolExecution; timestamp: string }> = [];

  messages.forEach((msg) => {
    combinedItems.push({
      type: 'message',
      data: msg,
      timestamp: msg.timestamp,
    });
  });

  toolExecutions.forEach((tool) => {
    combinedItems.push({
      type: 'tool',
      data: tool,
      timestamp: tool.timestamp || tool.started_at || '',
    });
  });

  combinedItems.sort((a, b) => {
    const timeA = new Date(a.timestamp).getTime();
    const timeB = new Date(b.timestamp).getTime();
    return timeA - timeB;
  });

  const getToolColor = (toolName: string) => {
    if (toolName.includes('terminal')) return 'border-l-terminal';
    if (toolName.includes('browser')) return 'border-l-browser';
    if (toolName.includes('python')) return 'border-l-python';
    if (toolName.includes('file_edit')) return 'border-l-file-edit';
    if (toolName.includes('proxy')) return 'border-l-proxy';
    if (toolName.includes('agents_graph')) return 'border-l-agents-graph';
    if (toolName.includes('thinking')) return 'border-l-thinking';
    if (toolName.includes('web_search')) return 'border-l-web-search';
    if (toolName.includes('finish')) return 'border-l-finish';
    if (toolName.includes('reporting')) return 'border-l-reporting';
    return 'border-l-border-color';
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'text-warning';
      case 'completed':
        return 'text-success';
      case 'failed':
        return 'text-error';
      default:
        return 'text-text-muted';
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      {combinedItems.length === 0 ? (
        <div className="text-center py-8 text-text-muted text-sm">
          No messages yet. Start a conversation with the agent.
        </div>
      ) : (
        combinedItems.map((item, index) => {
          if (item.type === 'message') {
            const message = item.data as ChatMessage;
            const isUser = message.role === 'user';
            const isStatus = message.role === 'system' || message.metadata?.type === 'status';

            if (isStatus) {
              return (
                <div
                  key={`message-${message.message_id}`}
                  className="self-center bg-bg-tertiary border border-info max-w-[90%] text-center text-info rounded-lg p-3"
                >
                  <div className="text-xs font-semibold text-info mb-1">
                    {message.metadata?.type === 'status' ? 'Status' : 'System'}
                  </div>
                  <div className="text-sm">{message.content}</div>
                </div>
              );
            }

            return (
              <div
                key={`message-${message.message_id}`}
                className={`flex flex-col max-w-[80%] rounded-lg p-3 animate-[slideIn_0.3s_ease-out] ${
                  isUser
                    ? 'self-end bg-bg-tertiary border border-primary-green'
                    : 'self-start bg-bg-secondary border border-border-color'
                }`}
              >
                <div className="text-xs text-text-muted mb-1">
                  {isUser ? 'You' : 'Assistant'} • {new Date(message.timestamp).toLocaleTimeString()}
                </div>
                <div className="text-sm whitespace-pre-wrap break-words">{message.content}</div>
              </div>
            );
          } else {
            const tool = item.data as ToolExecution;
            return (
              <div
                key={`tool-${tool.execution_id}`}
                className={`p-3 rounded-lg border-l-4 bg-bg-secondary my-2 animate-[slideIn_0.3s_ease-out] ${getToolColor(tool.tool_name)}`}
              >
                <div className="flex items-center gap-2 mb-2 font-semibold">
                  <span className="text-sm">🔧</span>
                  <span className="text-sm">{tool.tool_name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded bg-bg-tertiary ${getStatusColor(tool.status)}`}>
                    {tool.status}
                  </span>
                </div>
                {Object.keys(tool.args || {}).length > 0 && (
                  <div className="text-xs text-text-secondary mt-2 font-mono">
                    <div className="text-text-muted mb-1">Arguments:</div>
                    <pre className="whitespace-pre-wrap break-all">
                      {JSON.stringify(tool.args, null, 2)}
                    </pre>
                  </div>
                )}
                {tool.result !== undefined && tool.status !== 'running' && (
                  <div className="mt-2 p-2 bg-bg-tertiary rounded text-xs font-mono whitespace-pre-wrap break-all">
                    <div className="text-text-muted mb-1">Result:</div>
                    {typeof tool.result === 'string'
                      ? tool.result
                      : JSON.stringify(tool.result, null, 2)}
                  </div>
                )}
              </div>
            );
          }
        })
      )}
    </div>
  );
}

