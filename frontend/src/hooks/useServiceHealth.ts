import { useEffect, useState } from 'react';
import { healthCheck } from '../services/api';

type Health = 'loading' | 'ok' | 'degraded' | 'error';

export function useServiceHealth(intervalMs = 30000) {
  const [status, setStatus] = useState<Health>('loading');

  const refresh = async () => {
    try {
      const data = await healthCheck();
      setStatus(data.lightrag === 'unavailable' ? 'degraded' : 'ok');
    } catch {
      setStatus('error');
    }
  };

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);

  return { status, refresh };
}
