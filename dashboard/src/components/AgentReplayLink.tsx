import { ExternalLink, Bot } from 'lucide-react';
import type { BrowserTask } from '@/lib/types';

/** Surfaces the Browserbase replay recording of a computer-use action. */
export function AgentReplayLink({ task }: { task: BrowserTask }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm">
      <span className="flex items-center gap-2 text-muted-foreground">
        <Bot className="h-4 w-4" />
        {task.ok ? 'Agent finished the errand' : 'Agent attempted the errand'}
        {task.mocked && <span className="text-xs">(simulated)</span>}
      </span>
      {task.replay_url ? (
        <a
          href={task.replay_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
        >
          Watch the agent <ExternalLink className="h-3.5 w-3.5" />
        </a>
      ) : (
        <span className="text-xs text-muted-foreground">no recording</span>
      )}
    </div>
  );
}
