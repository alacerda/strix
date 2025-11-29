'use client';

import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import type { ChatMessage, ToolExecution } from '@/types';

interface ChatContainerProps {
  messages: ChatMessage[];
  toolExecutions: ToolExecution[];
  onSendMessage: (message: string) => void;
  disabled?: boolean;
}

export function ChatContainer({
  messages,
  toolExecutions,
  onSendMessage,
  disabled,
}: ChatContainerProps) {
  return (
    <div className="flex flex-col h-full bg-bg-primary">
      <MessageList messages={messages} toolExecutions={toolExecutions} />
      <MessageInput onSend={onSendMessage} disabled={disabled} />
    </div>
  );
}

